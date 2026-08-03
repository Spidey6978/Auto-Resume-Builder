import json
import hashlib
import logging
from typing import List
from models.domain import CanonicalProfile, TargetContext, Project, Fact
from core.ai_gateway import AIGateway
from core.cache import CacheManager

logger = logging.getLogger(__name__)

class TargetEngine:
    """
    Applies targeting rules to a CanonicalProfile.
    Filters projects based on explicit rules and scores facts based on relevance to a target role.
    """
    CACHE_NAMESPACE = "target_engine_scoring"
    PROMPT_VERSION = "scoring-v1.0"

    def __init__(self, ai_gateway: AIGateway, cache_manager: CacheManager):
        self.ai = ai_gateway
        self.cache = cache_manager

    def _filter_projects(self, projects: List[Project], target: TargetContext) -> List[Project]:
        rules = target.project_rules
        filtered = []
        for p in projects:
            if rules.exclude and p.id in rules.exclude:
                logger.info(f"TargetEngine: Excluded project '{p.id}' based on rules.")
                continue
            if rules.include_only and p.id not in rules.include_only:
                continue
            filtered.append(p)
        return filtered

    def _score_project_facts(self, project: Project, target: TargetContext, mock_ai: bool = False, max_facts: int = 5) -> List[Fact]:
        """
        Uses the AI to score and select the top `max_facts` most relevant facts for the target role.
        """
        if len(project.facts) <= max_facts:
            return project.facts

        # Fingerprint the JD + the facts
        sorted_facts = sorted(project.facts, key=lambda f: f.id)
        fact_payload = [{"id": f.id, "text": f.text} for f in sorted_facts]
        payload = {
            "target_id": target.id,
            "target_desc": target.description,
            "facts": fact_payload,
            "version": self.PROMPT_VERSION
        }
        cache_key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
        
        cached_selection = self.cache.get(self.CACHE_NAMESPACE, cache_key)
        if cached_selection and isinstance(cached_selection, list):
            # Map IDs back to Fact objects
            selected = [f for f in project.facts if f.id in cached_selection]
            if selected:
                return selected[:max_facts]

        fact_text = "\n".join([f"[{f.id}] {f.text}" for f in project.facts])
        prompt = f"""
You are an expert technical recruiter matching candidate experiences to a Job Description.

JOB DESCRIPTION / TARGET ROLE:
{target.description}

PROJECT FACTS:
{fact_text}

TASK:
Select up to {max_facts} fact IDs that are MOST relevant to the target role. 
Prioritize facts that demonstrate skills, scale, or technologies mentioned in the job description.

RETURN FORMAT:
Return ONLY a valid JSON array of strings representing the selected fact IDs, ordered by most relevant to least relevant.
Example: ["fact_1", "fact_3", "fact_2"]
"""
        try:
            response_text = self.ai.generate_text(prompt, mock_ai=mock_ai, model_hint="scoring")
            if mock_ai:
                selected_ids = [f.id for f in project.facts[:max_facts]]
            else:
                # Naive JSON extraction
                json_start = response_text.find('[')
                json_end = response_text.rfind(']') + 1
                if json_start != -1 and json_end != -1:
                    selected_ids = json.loads(response_text[json_start:json_end])
                else:
                    selected_ids = []
            
            # Save to cache
            if selected_ids:
                self.cache.set(self.CACHE_NAMESPACE, cache_key, selected_ids)
                
            selected_facts = [f for f in project.facts if f.id in selected_ids]
            # Fallback if parsing failed
            return selected_facts[:max_facts] if selected_facts else project.facts[:max_facts]
            
        except Exception as e:
            logger.error(f"TargetEngine fact scoring failed: {e}")
            return project.facts[:max_facts]

    def apply_target(self, profile: CanonicalProfile, target: TargetContext, mock_ai: bool = False) -> CanonicalProfile:
        """
        Returns a new targeted CanonicalProfile with pruned projects and ranked/filtered facts.
        """
        # We don't want to mutate the global in-memory profile, so we build a shallow-ish copy
        targeted_projects = []
        filtered_projects = self._filter_projects(profile.projects, target)
        
        for proj in filtered_projects:
            best_facts = self._score_project_facts(proj, target, mock_ai=mock_ai)
            
            targeted_proj = Project(
                id=proj.id,
                name=proj.name,
                link=proj.link,
                tech_stack=proj.tech_stack,
                category=proj.category,
                facts=best_facts
            )
            targeted_projects.append(targeted_proj)

        # Build a new profile with the targeted data
        # For now, we only filter projects. Experience and awards just pass through.
        return CanonicalProfile(
            schema_version=profile.schema_version,
            personal=profile.personal,
            education=profile.education,
            experience=profile.experience,  # Future: filter these too
            awards=profile.awards,
            projects=targeted_projects,
            skills=profile.skills
        )
