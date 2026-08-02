import os
import time
import random
import re
import google.generativeai as genai
from typing import List, Optional, Tuple
from core.cache import CacheManager

PROMPT_VERSION = "bullets-v1.0"
_AVAILABLE_MODELS_CACHE = None


def get_available_models(api_key: str) -> List[str]:
    global _AVAILABLE_MODELS_CACHE
    if _AVAILABLE_MODELS_CACHE is not None:
        return _AVAILABLE_MODELS_CACHE

    genai.configure(api_key=api_key)
    try:
        _AVAILABLE_MODELS_CACHE = [
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
    except Exception as e:
        print(f"  [!] Could not fetch available Gemini models: {e}")
        _AVAILABLE_MODELS_CACHE = []

    return _AVAILABLE_MODELS_CACHE


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

    # Transient error signatures
    transient_keywords = [
        "429", "500", "502", "503", "504", "resource_exhausted",
        "quota", "rate limit", "deadline_exceeded", "unavailable", "temporarily"
    ]
    for kw in transient_keywords:
        if kw in err_str:
            return "transient", retry_after

    # Default to transient for unknown network errors
    return "transient", retry_after


class AIGateway:
    """
    Unified AI Gateway for Google Gemini API.
    Handles input caching, transient retry backoffs, and rate-limit safety.
    """

    def generate_text(self, prompt: str, mock_ai: bool = False, model_hint: str = "") -> str:
        """
        Generic text generation with rate limiting, retries, and fallback cascade.
        Does NOT handle caching (callers should handle their own cache semantics).
        """
        if mock_ai:
            return f"Mocked AI response for {model_hint}\n- Mock bullet 1\n- Mock bullet 2"

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY missing in environment.")

        genai.configure(api_key=api_key)

        available_models = get_available_models(api_key)
        preferred_order = [
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro",
            "gemini-1.0-pro"
        ]

        models_to_try = [m for m in preferred_order if m in available_models]
        if not models_to_try and available_models:
            models_to_try.append(available_models[0])
        if not models_to_try:
            models_to_try = ["gemini-pro"]

        for model_name in models_to_try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    return response.text
                except Exception as e:
                    error_type, retry_after_sec = classify_exception(e)

                    if error_type == "fatal":
                        print(f"  [!] {model_name} fatal error for '{model_hint}': {e}. Skipping model.")
                        break  # Stop retrying this model, jump to next model in cascade

                    # Transient error handling with exponential backoff + jitter
                    if attempt < max_retries - 1:
                        backoff = retry_after_sec or (2 ** attempt + random.uniform(0.1, 0.5))
                        print(f"  [!] {model_name} transient error (429/503): {e}. Retrying in {backoff:.1f}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(backoff)
                    else:
                        print(f"  [!] {model_name} failed after {max_retries} attempts. Trying next model in cascade...")

        raise RuntimeError(f"All Gemini models failed to generate text for '{model_hint}' due to API errors.")
