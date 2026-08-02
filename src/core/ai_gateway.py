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
    Handles input caching, version fingerprinting, transient retry backoffs, and rate-limit safety.
    Never manufactures generic/fabricated fallback bullets when data is missing or API fails.
    """

    CACHE_NAMESPACE = "llm_bullets"

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()

    def generate_bullets_from_readme(
        self,
        repo_name: str,
        readme_content: str,
        is_umbrella: bool = False,
        target_salt: str = "general",
        mock_ai: bool = False
    ) -> List[str]:
        """
        Generates 2 ATS-optimized resume bullet points from raw README content.
        Uses local cache if available; otherwise queries Gemini with bounded retries.
        """
        if mock_ai:
            print(f"  [MOCK AI] Generating simulated bullets for '{repo_name}'")
            return [
                f"Simulated bullet point 1 for {repo_name} highlighting technical features and architecture.",
                f"Simulated bullet point 2 for {repo_name} demonstrating impact and performance optimization."
            ]

        # Explicit failure status if README is insufficient (Rule: No fabricated bullets)
        if not readme_content or len(readme_content.strip()) < 50:
            print(f"  [!] Insufficient README data for '{repo_name}'. Cannot generate reliable bullets.")
            return [f"⚠️ Insufficient source material to generate reliable bullets for {repo_name}."]

        truncated_readme = readme_content[:40000]
        context_type = "a grouped full-stack project" if is_umbrella else "a technical repository"

        prompt = f"""
        You are an elite ATS resume writer and senior engineering recruiter. I have {context_type} named '{repo_name}'.
        Here is the content of the README.md:
        
        {truncated_readme}
        
        Your task: Generate exactly 2 professional, highly technical resume bullet points summarizing the architecture, logic, and impact of this project.
        Rules:
        - Analyze the entire README. Deeply extract the complex logic, math, physics, or architectural patterns used (ignore fluff and licenses).
        - Start each bullet with a strong, VARIED past-tense action verb (e.g., Architected, Designed, Orchestrated, Optimized, Spearheaded, Integrated). DO NOT repeat the same starting verb across bullets.
        - Quantify impact where possible and aggressively highlight the tech stack/frameworks.
        - Never invent compound architectural terms. Use precise standard terminology only.
        - DO NOT include markdown formatting like asterisks (*), bolding, or hyphens at the start.
        - STRICT LENGTH LIMIT: Keep each bullet punchy, around 15-25 words, so it fits exactly on a single line in a PDF.
        - Return ONLY the 2 bullet points, separated by a newline.
        """

        # 1. Compute Cache Key fingerprint including PROMPT_VERSION, target_salt, prompt_hash, and content
        prompt_hash = CacheManager.hash_key(prompt)
        cache_key = f"{PROMPT_VERSION}||{target_salt}||{prompt_hash}||{repo_name}||{truncated_readme}"

        # 2. Check Cache
        cached_bullets = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached_bullets and isinstance(cached_bullets, list):
            print(f"  [CACHE HIT] Loaded cached bullets for '{repo_name}'")
            return cached_bullets

        print(f"  [API CALL] Querying Gemini for '{repo_name}'...")
        try:
            response_text = self.generate_text(prompt, mock_ai=mock_ai, model_hint=repo_name)
            bullets = response_text.strip().split("\n")
            cleaned_bullets = [b.lstrip("- *•").strip() for b in bullets if b.strip()][:2]

            if cleaned_bullets:
                # Save to Cache on success
                self.cache.set(self.CACHE_NAMESPACE, cache_key, cleaned_bullets)
                return cleaned_bullets
        except Exception as e:
            print(f"  [!] Exception during bullet generation for '{repo_name}': {e}")

        # Explicit failure status (Never manufacture false bullet claims!)
        print(f"  [!] All Gemini models failed for '{repo_name}'. Returning failure status.")
        return [f"⚠️ Could not generate reliable bullets for {repo_name} due to API rate limits or errors."]

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
