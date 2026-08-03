import json
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

from models.domain import Project, Fact
from core.ai_gateway import AIGateway
from core.cache import CacheManager


class GenerationStatus(str, Enum):
    SUCCESS = "success"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_RESPONSE = "invalid_response"
    AI_ERROR = "ai_error"


@dataclass
class GenerationResult:
    bullets: List[str]
    status: GenerationStatus
    error: Optional[str] = None


class ContentGenerator:
    """
    Generates presentation-ready resume bullets strictly from canonical Facts.
    Owns the formatting semantics and generation caching.
    """
    CACHE_NAMESPACE = "llm_rendered_bullets"
    PROMPT_VERSION = "render-v1.0"

    def __init__(self, ai_gateway: AIGateway, cache_manager: CacheManager):
        self.ai = ai_gateway
        self.cache = cache_manager

    def _fingerprint(self, project: Project, target: str) -> str:
        # Create a deterministic payload for hashing based ONLY on semantic inputs
        payload = {
            "version": self.PROMPT_VERSION,
            "target": target,
            "project_id": project.id,
            "tech_stack": sorted(project.tech_stack),
            "facts": [
                {
                    "id": f.id,
                    "text": f.text,
                    "metric": f.metric
                }
                for f in sorted(project.facts, key=lambda x: x.id)
            ]
        }
        payload_str = json.dumps(payload, sort_keys=True)
        return CacheManager.hash_key(payload_str)

    def generate_project_bullets(self, project: Project, target: str = "general", mock_ai: bool = False) -> GenerationResult:
        """
        Generates ATS-optimized resume bullets from a Project's facts.
        """
        if not project.facts:
            return GenerationResult(bullets=[], status=GenerationStatus.INSUFFICIENT_DATA)

        cache_key = self._fingerprint(project, target)
        cached = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached is not None and isinstance(cached, list):
            return GenerationResult(bullets=cached, status=GenerationStatus.SUCCESS)

        # Build context
        tech_context = ", ".join(project.tech_stack) if project.tech_stack else "None specified"
        facts_text = "\n".join(f"- {f.text} (Metric: {f.metric or 'None'})" for f in project.facts)

        prompt = f"""
        You are an elite ATS resume writer and senior engineering recruiter.
        Your task is to generate concise resume bullets emphasizing technical impact and relevant terminology.
        
        CRITICAL RULE: You must make ONLY claims supported by the supplied facts. Do NOT invent or infer features.
        
        Project Context:
        Name: {project.name}
        Technologies: {tech_context}
        Target Role Focus: {target}
        
        Extracted Facts:
        {facts_text}
        
        Rules:
        - Generate exactly 2 professional, highly technical resume bullet points.
        - Start each bullet with a strong, VARIED past-tense action verb (e.g., Architected, Engineered, Optimized, Integrated).
        - Optimize for clarity, technical specificity, impact, and brevity.
        - Keep each bullet punchy, around 15-25 words.
        - DO NOT include markdown formatting like asterisks (*), bolding, or hyphens at the start.
        - Return ONLY the bullet points separated by a newline.
        """

        try:
            response_text = self.ai.generate_text(prompt, mock_ai=mock_ai, model_hint=project.name)
        except Exception as e:
            return GenerationResult(bullets=[], status=GenerationStatus.AI_ERROR, error=str(e))

        # Clean bullets
        bullets = response_text.strip().split("\n")
        cleaned_bullets = [b.lstrip("- *•").strip() for b in bullets if b.strip()][:2]

        if not cleaned_bullets:
            return GenerationResult(bullets=[], status=GenerationStatus.INVALID_RESPONSE, error="Empty response")

        self.cache.set(self.CACHE_NAMESPACE, cache_key, cleaned_bullets)
        return GenerationResult(bullets=cleaned_bullets, status=GenerationStatus.SUCCESS)
