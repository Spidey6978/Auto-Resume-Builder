import json
import hashlib
import logging
from typing import List
from models.domain import CanonicalProfile, TargetContext, Project, Fact
from models.plan import ResumePlan, PlannedProject, PlannedFact
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

    def _score_project_facts(self, project: Project, target: TargetContext, mock_ai: bool = False, max_facts: int = 5) -> tuple[List[Fact], str]:
        """
        Uses the AI to score and select the top `max_facts` most relevant facts for the target role.
        """
        if len(project.facts) <= max_facts:
            return project.facts, "success_unfiltered"

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
            # Map IDs back to Fact objects preserving LLM ranking order
            fact_map = {f.id: f for f in project.facts}
            selected = [fact_map[fid] for fid in cached_selection if fid in fact_map]
            if selected:
                return selected[:max_facts], "cache_hit"

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
                
            fact_map = {f.id: f for f in project.facts}
            selected_facts = [fact_map[fid] for fid in selected_ids if fid in fact_map]
            # Fallback if parsing failed
            if selected_facts:
                return selected_facts[:max_facts], "success"
            return project.facts[:max_facts], "fallback_unranked"
            
        except Exception as e:
            logger.error(f"TargetEngine fact scoring failed: {e}")
            return project.facts[:max_facts], "fallback_unranked"

    def create_plan(self, profile: CanonicalProfile, target: TargetContext, mock_ai: bool = False) -> ResumePlan:
        """
        Returns a ResumePlan dictating which projects and facts should be included.
        Does not mutate the CanonicalProfile.
        """
        planned_projects = []
        filtered_projects = self._filter_projects(profile.projects, target)
        
        for proj in filtered_projects:
            best_facts, status = self._score_project_facts(proj, target, mock_ai=mock_ai)
            
            planned_facts = [PlannedFact(fact_id=f.id, targeting_status=status) for f in best_facts]
            
            planned_proj = PlannedProject(
                project_id=proj.id,
                selected_facts=planned_facts
            )
            planned_projects.append(planned_proj)

        # Build a new plan with the targeted data
        return ResumePlan(
            target=target,
            projects=planned_projects
        )
