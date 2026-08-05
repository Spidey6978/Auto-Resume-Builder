import json
import hashlib
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional

from arb.models.domain import CanonicalProfile, Project, Fact, TargetContext
from arb.models.plan import ResumePlan, PlannedProject
from arb.core.ai_gateway import AIGateway
from arb.core.cache import CacheManager


class GenerationStatus(str, Enum):
    SUCCESS = "success"
    INSUFFICIENT_DATA = "insufficient_data"
    INVALID_RESPONSE = "invalid_response"
    AI_ERROR = "ai_error"


from arb.models.presentation import RenderedBullet

@dataclass
class GenerationResult:
    bullets: List[RenderedBullet]
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

    def generate_project_bullets(self, profile: CanonicalProfile, planned_project: PlannedProject, target: TargetContext, mock_ai: bool = False) -> GenerationResult:
        """
        Generates 2 highly condensed, ATS-optimized bullets for a single project,
        using ONLY the objective facts provided in the plan.
        """
        project = next((p for p in profile.projects if p.id == planned_project.project_id), None)
        if not project:
            return GenerationResult([], GenerationStatus.INSUFFICIENT_DATA)
            
        fact_ids = [pf.fact_id for pf in planned_project.selected_facts]
        fact_map = {f.id: f for f in project.facts}
        selected_facts = [fact_map[fid] for fid in fact_ids if fid in fact_map]
        
        # We temporarily inject selected facts to use the existing fingerprint method
        temp_proj = Project(
            id=project.id,
            name=project.name,
            tech_stack=project.tech_stack,
            facts=selected_facts
        )
        
        # If there are no facts, we cannot generate truthful bullets.
        if not selected_facts:
            return GenerationResult([], GenerationStatus.INSUFFICIENT_DATA)
            
        cache_key = self._fingerprint(temp_proj, target)
        
        cached_bullets = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached_bullets and isinstance(cached_bullets, list):
            # We assume it's a list of dicts now
            rendered_bullets = []
            for b_dict in cached_bullets:
                # handle legacy cache migration if it was a list of strings
                if isinstance(b_dict, str):
                    rb = RenderedBullet(text=b_dict, source_fact_ids=[], relevance_score=0.0)
                else:
                    rb = RenderedBullet.from_dict(b_dict)
                rendered_bullets.append(rb)
            return GenerationResult(rendered_bullets, GenerationStatus.SUCCESS)
            
        # Fact payload for the LLM
        fact_text = "\n".join([f"- [{f.id}] {f.text} (Metric: {f.metric or 'N/A'})" for f in selected_facts])
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
        - Return ONLY a JSON array of objects with this schema:
        [
          {{
            "text": "The bullet text without markdown formatting",
            "source_fact_ids": ["fact_id_1", "fact_id_2"]
          }}
        ]
        """

        try:
            response_text = self.ai.generate_text(prompt, mock_ai=mock_ai, model_hint=project.name)
            # Try to extract JSON array
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start != -1 and json_end != -1:
                parsed_array = json.loads(response_text[json_start:json_end])
            else:
                parsed_array = []
        except Exception as e:
            return GenerationResult(bullets=[], status=GenerationStatus.AI_ERROR, error=str(e))

        if not parsed_array:
            return GenerationResult(bullets=[], status=GenerationStatus.INVALID_RESPONSE, error="Empty or invalid JSON response")

        # Map to RenderedBullet
        rendered_bullets = []
        for item in parsed_array:
            text = item.get("text", "").strip()
            if not text:
                continue
                
            src_ids = item.get("source_fact_ids", [])
            # Calculate relevance: max of source facts
            scores = []
            for sid in src_ids:
                pf = next((pf for pf in planned_project.selected_facts if pf.fact_id == sid), None)
                if pf:
                    scores.append(pf.relevance_score)
            
            rel_score = max(scores) if scores else 0.0
            
            rb = RenderedBullet(
                text=text,
                source_fact_ids=src_ids,
                relevance_score=rel_score
            )
            rendered_bullets.append(rb)

        self.cache.set(self.CACHE_NAMESPACE, cache_key, [b.to_dict() for b in rendered_bullets])
        return GenerationResult(bullets=rendered_bullets, status=GenerationStatus.SUCCESS)

    def generate_experience_bullets(self, profile: CanonicalProfile, planned_experience: PlannedExperience, target: TargetContext, mock_ai: bool = False) -> GenerationResult:
        """
        Generates ATS-optimized bullets for an experience item.
        """
        exp = next((e for e in profile.experience if e.id == planned_experience.experience_id), None)
        if not exp:
            return GenerationResult([], GenerationStatus.INSUFFICIENT_DATA)
            
        fact_ids = [pf.fact_id for pf in planned_experience.selected_facts]
        fact_map = {f.id: f for f in exp.facts}
        selected_facts = [fact_map[fid] for fid in fact_ids if fid in fact_map]
        
        if not selected_facts:
            return GenerationResult([], GenerationStatus.INSUFFICIENT_DATA)
            
        # Simplified hash just for experience facts
        sorted_facts = sorted(selected_facts, key=lambda f: f.id)
        fact_payload = [{"id": f.id, "text": f.text, "type": f.fact_type, "metric": f.metric} for f in sorted_facts]
        payload = {
            "exp_id": exp.id,
            "target_id": target.id,
            "target_desc": target.description,
            "facts": fact_payload,
            "prompt_version": self.PROMPT_VERSION + "-exp"
        }
        cache_key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
        
        cached_bullets = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached_bullets and isinstance(cached_bullets, list):
            rendered_bullets = [RenderedBullet.from_dict(d) for d in cached_bullets]
            return GenerationResult(rendered_bullets, GenerationStatus.SUCCESS)
            
        fact_text = "\n".join([f"- [{f.id}] {f.text} (Metric: {f.metric or 'N/A'})" for f in selected_facts])
        
        prompt = f"""
        You are an elite ATS resume writer and senior engineering recruiter.
        Your task is to generate concise resume bullets emphasizing technical impact and relevant terminology.
        
        CRITICAL RULE: You must make ONLY claims supported by the supplied facts. Do NOT invent or infer features.
        
        Experience Context:
        Organization: {exp.organization}
        Role: {exp.role}
        Target Role Focus: {target.description}
        
        Extracted Facts:
        {fact_text}
        
        Rules:
        - Generate 2-3 professional, highly technical resume bullet points.
        - Start each bullet with a strong, VARIED past-tense action verb (e.g., Architected, Engineered, Optimized, Integrated).
        - Optimize for clarity, technical specificity, impact, and brevity.
        - Keep each bullet punchy, around 15-25 words.
        - Return ONLY a JSON array of objects with this schema:
        [
          {{
            "text": "The bullet text without markdown formatting",
            "source_fact_ids": ["fact_id_1", "fact_id_2"]
          }}
        ]
        """

        try:
            response_text = self.ai.generate_text(prompt, mock_ai=mock_ai, model_hint=exp.organization)
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start != -1 and json_end != -1:
                parsed_array = json.loads(response_text[json_start:json_end])
            else:
                parsed_array = []
        except Exception as e:
            return GenerationResult(bullets=[], status=GenerationStatus.AI_ERROR, error=str(e))

        if not parsed_array:
            return GenerationResult(bullets=[], status=GenerationStatus.INVALID_RESPONSE, error="Empty or invalid JSON response")

        rendered_bullets = []
        for item in parsed_array:
            text = item.get("text", "").strip()
            if not text:
                continue
            src_ids = item.get("source_fact_ids", [])
            scores = []
            for sid in src_ids:
                pf = next((pf for pf in planned_experience.selected_facts if pf.fact_id == sid), None)
                if pf:
                    scores.append(pf.relevance_score)
            rel_score = max(scores) if scores else 0.0
            
            rb = RenderedBullet(
                text=text,
                source_fact_ids=src_ids,
                relevance_score=rel_score
            )
            rendered_bullets.append(rb)

        self.cache.set(self.CACHE_NAMESPACE, cache_key, [b.to_dict() for b in rendered_bullets])
        return GenerationResult(bullets=rendered_bullets, status=GenerationStatus.SUCCESS)
