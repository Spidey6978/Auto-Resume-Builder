import os
import time
import random
import re
import logging
from google import genai
from google.genai.errors import APIError
from typing import List, Optional, Tuple

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
    Handles transient retry backoffs and rate-limit safety.
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    def generate_text(self, prompt: str, mock_ai: bool = False, model_hint: str = "") -> str:
        """
        Generic text generation with rate limiting, retries, and fallback cascade.
        Does NOT handle caching (callers should handle their own cache semantics).
        """
        preferred_order = [
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ]

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
                        break  # Stop retrying this model, jump to next model in cascade

                    # Transient error handling with exponential backoff + jitter
                    if attempt < max_retries - 1:
                        backoff = retry_after_sec or (2 ** attempt + random.uniform(0.1, 0.5))
                        logger.warning(f"{model_name} transient error (429/503): {e}. Retrying in {backoff:.1f}s (attempt {attempt + 1}/{max_retries})...")
                        time.sleep(backoff)
                    else:
                        logger.warning(f"{model_name} failed after {max_retries} attempts. Trying next model in cascade...")

        raise RuntimeError(f"All Gemini models failed to generate text for '{model_hint}' due to API errors.")

class MockAIGateway:
    """Fake AIGateway for deterministic, offline testing."""
    def __init__(self):
        pass

    def generate_text(self, prompt: str, mock_ai: bool = False, model_hint: str = "") -> str:
        return f"Mocked AI response for {model_hint}\n- Mock bullet 1\n- Mock bullet 2"
