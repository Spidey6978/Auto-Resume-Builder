import os
import time
import random
import re
import logging
import requests
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple, Dict, Any

from arb.core.ai_config import AIConfig, load_ai_config, DEFAULT_LOCAL_MODEL, DEFAULT_LOCAL_URL

logger = logging.getLogger(__name__)


def classify_exception(exc: Exception) -> Tuple[str, Optional[int]]:
    """
    Classifies exceptions into 'transient' (retryable, e.g. 429 rate limit, 503 unavailable)
    vs 'fatal' (non-retryable, e.g. 400 bad request, 401 unauthorized, 403 forbidden).
    Also extracts Retry-After seconds if available in exception message.
    """
    err_str = str(exc).lower()

    # Parse potential Retry-After header/message
    retry_after = None
    match = re.search(r'retry[-_]after[:\s]+(\d+)', err_str)
    if match:
        try:
            retry_after = int(match.group(1))
        except ValueError:
            retry_after = None

    # Fatal error signatures
    fatal_keywords = [
        "400", "401", "403", "unauthorized", "invalid_argument",
        "permission_denied", "api_key_not_valid", "invalid api key"
    ]
    for kw in fatal_keywords:
        if kw in err_str:
            return "fatal", retry_after

    # Hard Quota Exhaustion
    if "resource_exhausted" in err_str or "quota" in err_str:
        if "per minute" not in err_str and "rate limit" not in err_str:
            return "fatal", retry_after

    # Transient error signatures
    transient_keywords = [
        "429", "500", "502", "503", "504",
        "rate limit", "deadline_exceeded", "unavailable", "temporarily"
    ]
    for kw in transient_keywords:
        if kw in err_str:
            return "transient", retry_after

    # Default to transient for unknown network errors
    return "transient", retry_after


class BaseLLMProvider(ABC):
    """Abstract interface for an LLM inference provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the provider is reachable and ready to handle requests."""
        pass

    @abstractmethod
    def list_models(self) -> List[str]:
        """Lists installed or available models for this provider."""
        pass

    @abstractmethod
    def generate_text(self, prompt: str, model_hint: str = "") -> str:
        """Generates text from a given prompt."""
        pass


class OllamaProvider(BaseLLMProvider):
    """
    Local inference provider backed by Ollama REST API.
    Zero cloud dependencies, runs 100% locally on device.
    """

    def __init__(self, base_url: str = DEFAULT_LOCAL_URL, model: str = DEFAULT_LOCAL_MODEL, timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        """Quick healthcheck ping to Ollama daemon."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            return resp.status_code == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Returns the list of currently installed model names in Ollama."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                return [m.get("name", "") for m in models if m.get("name")]
        except Exception as e:
            logger.debug(f"Failed to fetch Ollama models: {e}")
        return []

    def is_model_installed(self, model_name: Optional[str] = None) -> bool:
        target = (model_name or self.model).lower()
        target_base = target.split(":")[0]
        installed = [m.lower() for m in self.list_models()]
        for m in installed:
            if m == target or m == f"{target}:latest" or m.startswith(f"{target_base}:"):
                return True
        return False

    def generate_text(self, prompt: str, model_hint: str = "") -> str:
        if not self.is_available():
            raise RuntimeError(
                f"Ollama is not running at {self.base_url}. "
                f"Start Ollama or run 'arb model setup'."
            )

        if not self.is_model_installed(self.model):
            raise RuntimeError(
                f"Model '{self.model}' is not installed in Ollama. "
                f"Run 'ollama pull {self.model}' or run 'arb model setup'."
            )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        }

        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ollama inference error for '{model_hint}': {e}")
            raise RuntimeError(f"Local Ollama inference failed for '{model_hint}': {e}")


class GeminiProvider(BaseLLMProvider):
    """
    Cloud inference provider backed by Google API (BYOK), prioritizing Gemma 4.
    """

    def __init__(self, api_key: Optional[str] = None, default_model: str = "gemma-4-26b-a4b-it"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.default_model = default_model
        self.client = None
        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini/Gemma Client: {e}")

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(self.api_key and self.client is not None)

    def list_models(self) -> List[str]:
        # Prioritize Gemma 4 models, followed by fast and stable Gemini fallback models
        candidates = [
            self.default_model,
            "gemma-4-26b-a4b-it",
            "gemma-4-31b-it",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.5-pro"
        ]
        seen = set()
        ordered = []
        for m in candidates:
            if m and m not in seen:
                seen.add(m)
                ordered.append(m)
        return ordered

    def generate_text(self, prompt: str, model_hint: str = "") -> str:
        if not self.is_available():
            raise RuntimeError(
                "Gemini API key is not configured. Set GEMINI_API_KEY or run 'arb init'."
            )

        preferred_order = self.list_models()

        for model_name in preferred_order:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    return response.text
                except Exception as e:
                    error_type, retry_after_sec = classify_exception(e)

                    if error_type == "fatal":
                        logger.error(f"{model_name} fatal error for '{model_hint}': {e}. Skipping model.")
                        break

                    if attempt < max_retries - 1:
                        backoff = retry_after_sec or (2 ** attempt + random.uniform(0.1, 0.5))
                        logger.warning(
                            f"{model_name} transient error (429/503): {e}. "
                            f"Retrying in {backoff:.1f}s (attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(backoff)
                    else:
                        logger.warning(f"{model_name} failed after {max_retries} attempts. Trying next model in cascade...")

        raise RuntimeError(f"All Gemini models failed to generate text for '{model_hint}' due to API errors.")


class MockProvider(BaseLLMProvider):
    """Fake provider for offline, deterministic testing."""

    @property
    def name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    def list_models(self) -> List[str]:
        return ["mock-v1"]

    def generate_text(self, prompt: str, model_hint: str = "") -> str:
        # Detect if caller expects a JSON array (like FactExtractor or ContentGenerator)
        prompt_lower = prompt.lower()
        if "json array" in prompt_lower or "provenance" in prompt_lower:
            return "[]"
        return f"Mocked AI response for {model_hint}\n- Mock bullet 1\n- Mock bullet 2"


class AIGateway:
    """
    Unified AI Gateway with Local-First Routing and Opportunistic BYOK Cloud Fallback.

    Modes:
      - 'auto' (default): Uses local Ollama model if available. If local is down or missing
                          and cloud fallback is enabled, uses configured Gemini API.
      - 'local': Uses local Ollama model only. Never sends career data to cloud.
      - 'cloud': Uses Gemini API only.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[AIConfig] = None,
        local_provider: Optional[BaseLLMProvider] = None,
        cloud_provider: Optional[BaseLLMProvider] = None
    ):
        self.config = config or load_ai_config()

        # Wire providers
        self.local_provider = local_provider or OllamaProvider(
            base_url=self.config.local_url,
            model=self.config.local_model
        )

        cloud_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.cloud_provider = cloud_provider or GeminiProvider(
            api_key=cloud_key,
            default_model=self.config.cloud_model
        )
        self.mock_provider = MockProvider()

        # For backwards compatibility with direct access
        self.api_key = cloud_key
        self.client = getattr(self.cloud_provider, "client", None)

    def resolve_provider(self) -> Tuple[BaseLLMProvider, str]:
        """
        Determines the active provider based on mode and runtime availability.
        Returns (provider, description).
        """
        mode = self.config.mode.lower()

        if mode == "local":
            if not self.local_provider.is_available():
                raise RuntimeError(
                    f"Local mode is forced, but Ollama is not reachable at {self.config.local_url}. "
                    "Start Ollama or run 'arb model status'."
                )
            return self.local_provider, f"Local ({self.config.local_model})"

        if mode == "cloud":
            if not self.cloud_provider.is_available():
                raise RuntimeError(
                    "Cloud mode is forced, but GEMINI_API_KEY is not set or invalid. "
                    "Run 'arb init' to set your key."
                )
            cloud_desc = f"Cloud ({self.config.cloud_model})"
            return self.cloud_provider, cloud_desc

        # Default: auto (Local-First with Cloud Fallback)
        if self.local_provider.is_available():
            # Check if model is downloaded
            if isinstance(self.local_provider, OllamaProvider) and self.local_provider.is_model_installed():
                return self.local_provider, f"Local ({self.config.local_model})"
            elif not isinstance(self.local_provider, OllamaProvider):
                return self.local_provider, f"Local ({self.local_provider.name})"

            # Ollama is running but target model is not yet pulled
            if self.config.cloud_fallback and self.cloud_provider.is_available():
                logger.info(
                    f"Ollama running but '{self.config.local_model}' is not pulled. "
                    f"Falling back to configured Cloud provider ({self.config.cloud_model})."
                )
                return self.cloud_provider, f"Cloud ({self.config.cloud_model} - fallback)"
            else:
                # User will get a clear 'model not installed' message from OllamaProvider
                return self.local_provider, f"Local ({self.config.local_model})"

        # Local Ollama is not running
        if self.config.cloud_fallback and self.cloud_provider.is_available():
            return self.cloud_provider, f"Cloud ({self.config.cloud_model} - fallback)"

        raise RuntimeError(
            "No AI backend is available.\n"
            f"  - Local Ollama is unreachable at {self.config.local_url}.\n"
            "  - No GEMINI_API_KEY configured for cloud fallback.\n"
            "Fix options:\n"
            "  1. Start Ollama with 'ollama serve' and pull your model ('arb model setup').\n"
            "  2. Provide a Gemini API key ('arb init').\n"
            "  3. Use '--mock-ai' for offline testing."
        )

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic info for status commands and doctor checks."""
        local_online = self.local_provider.is_available()
        installed_models = self.local_provider.list_models() if local_online else []
        model_ready = False
        if local_online and isinstance(self.local_provider, OllamaProvider):
            model_ready = self.local_provider.is_model_installed(self.config.local_model)

        cloud_ready = self.cloud_provider.is_available()

        active_provider_desc = "None"
        try:
            _, active_provider_desc = self.resolve_provider()
        except Exception as e:
            active_provider_desc = f"Unavailable ({e})"

        return {
            "mode": self.config.mode,
            "local_provider": self.config.local_provider,
            "local_url": self.config.local_url,
            "local_model": self.config.local_model,
            "local_online": local_online,
            "local_installed_models": installed_models,
            "local_model_ready": model_ready,
            "cloud_provider": self.config.cloud_provider,
            "cloud_model": self.config.cloud_model,
            "cloud_ready": cloud_ready,
            "cloud_fallback": self.config.cloud_fallback,
            "active_route": active_provider_desc
        }

    def generate_text(self, prompt: str, mock_ai: bool = False, model_hint: str = "") -> str:
        """
        Generic text generation with local-first routing.
        """
        if mock_ai:
            return self.mock_provider.generate_text(prompt, model_hint=model_hint)

        provider, route_desc = self.resolve_provider()
        logger.debug(f"Routing '{model_hint}' inference to: {route_desc}")
        try:
            return provider.generate_text(prompt, model_hint=model_hint)
        except Exception as e:
            if (
                self.config.mode.lower() == "auto"
                and provider != self.cloud_provider
                and self.config.cloud_fallback
                and self.cloud_provider.is_available()
            ):
                logger.warning(
                    f"Local inference failed ({e}). Retrying with cloud fallback provider ({self.config.cloud_model})..."
                )
                return self.cloud_provider.generate_text(prompt, model_hint=model_hint)
            raise


class MockAIGateway:
    """Fake AIGateway for deterministic, offline testing."""
    def __init__(self):
        self.mock_provider = MockProvider()

    def generate_text(self, prompt: str, mock_ai: bool = False, model_hint: str = "") -> str:
        return self.mock_provider.generate_text(prompt, model_hint=model_hint)
