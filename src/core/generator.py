import json
import hashlib
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

from models.domain import Project, Fact, TargetContext
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

    def _fingerprint(self, project: Project, target: TargetContext) -> str:
        # Create a deterministic payload for hashing based ONLY on semantic inputs
        # (project facts and target role).
        
        # Sort facts by ID to ensure order doesn't affect hash
        sorted_facts = sorted(project.facts, key=lambda f: f.id)
        
        # We only hash the content of the facts, ignoring source provenance
        fact_payload = [{"id": f.id, "text": f.text, "type": f.fact_type, "metric": f.metric} for f in sorted_facts]
        
        payload = {
            "project_name": project.name,
            "target_id": target.id,
            "target_desc": target.description,
            "facts": fact_payload,
            "prompt_version": self.PROMPT_VERSION
        }
        
        payload_str = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(payload_str.encode('utf-8')).hexdigest()

    def generate_project_bullets(self, project: Project, target: TargetContext, mock_ai: bool = False) -> GenerationResult:
        """
        Generates 2 highly condensed, ATS-optimized bullets for a single project,
        using ONLY the objective facts provided in the domain model.
        """
        # If there are no facts, we cannot generate truthful bullets.
        if not project.facts:
            return GenerationResult([], GenerationStatus.INSUFFICIENT_DATA)
            
        cache_key = self._fingerprint(project, target)
        
        cached_bullets = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached_bullets:
            return GenerationResult(cached_bullets, GenerationStatus.SUCCESS)
            
        # Fact payload for the LLM
        fact_text = "\n".join([f"- [{f.fact_type}] {f.text} (Metric: {f.metric or 'N/A'})" for f in project.facts])
        tech_context = ", ".join(project.tech_stack) if project.tech_stack else "None specified"
        
        prompt = f"""
        You are an elite ATS resume writer and senior engineering recruiter.
        Your task is to generate concise resume bullets emphasizing technical impact and relevant terminology.
        
        CRITICAL RULE: You must make ONLY claims supported by the supplied facts. Do NOT invent or infer features.
        
        Project Context:
        Name: {project.name}
        Technologies: {tech_context}
        Target Role Focus: {target.description}
        
        Extracted Facts:
        {fact_text}
        
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
