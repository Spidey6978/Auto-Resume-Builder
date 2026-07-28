import os
import google.generativeai as genai
from typing import List, Optional
from core.cache import CacheManager

# Model list cache across sessions in memory
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


class AIGateway:
    """
    Unified AI Gateway for Google Gemini API.
    Handles input caching, rate-limit fallback cascades, and prompt execution.
    """

    CACHE_NAMESPACE = "llm_bullets"

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        self.cache = cache_manager or CacheManager()

    def generate_bullets_from_readme(
        self, repo_name: str, readme_content: str, is_umbrella: bool = False, mock_ai: bool = False
    ) -> List[str]:
        """
        Generates 2 ATS-optimized resume bullet points from raw README content.
        Uses local cache if available; otherwise queries Gemini.
        """
        if mock_ai:
            print(f"  [MOCK AI] Generating simulated bullets for '{repo_name}'")
            return [
                f"Simulated bullet point 1 for {repo_name} highlighting technical features and architecture.",
                f"Simulated bullet point 2 for {repo_name} demonstrating impact and performance optimization."
            ]

        if not readme_content or len(readme_content.strip()) < 50:
            return [
                "Architected core system components and maintained repository.",
                "Optimized application performance and resolved technical debt."
            ]

        # 1. Compute Cache Key based on inputs
        truncated_readme = readme_content[:40000]
        context_type = "a grouped full-stack project" if is_umbrella else "a technical repository"
        cache_key = f"{repo_name}||{context_type}||{truncated_readme}"

        # 2. Check Cache
        cached_bullets = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached_bullets and isinstance(cached_bullets, list):
            print(f"  [CACHE HIT] Loaded cached bullets for '{repo_name}'")
            return cached_bullets

        # 3. Check API Key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("  [!] GEMINI_API_KEY not found in environment. Using fallback descriptions.")
            return ["Add GEMINI_API_KEY to your .env file to generate bullets!"]

        genai.configure(api_key=api_key)

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

        print(f"  [API CALL] Querying Gemini for '{repo_name}'...")
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                bullets = response.text.strip().split("\n")
                cleaned_bullets = [b.lstrip("- *•").strip() for b in bullets if b.strip()][:2]

                if cleaned_bullets:
                    # 4. Save to Cache on success
                    self.cache.set(self.CACHE_NAMESPACE, cache_key, cleaned_bullets)
                    return cleaned_bullets

            except Exception as e:
                print(f"  [!] {model_name} failed for '{repo_name}': {e}. Trying next model...")

        print(f"  [!] All Gemini models failed or rate-limited for '{repo_name}'. Using fallback bullets.")
        fallback = [
            "Engineered core features and optimized system architecture.",
            "Resolved critical technical issues to ensure platform stability."
        ]
        return fallback
