import json
import hashlib
import logging
from typing import List
from models.domain import CanonicalProfile, TargetContext, Project, Fact
from models.plan import ResumePlan, PlannedProject, PlannedFact
from core.ai_gateway import AIGateway
from core.cache import CacheManager
from core.knowledge.evaluator import PolicyEvaluator
from core.fact_ranker import FactRanker

logger = logging.getLogger(__name__)

class TargetEngine:
    """
    Core engine for applying a TargetContext to a CanonicalProfile.
    Scores and filters facts/projects based on the target description.
    """
    CACHE_NAMESPACE = "llm_fact_scoring"
    PROMPT_VERSION = "scoring-v1.0"

    def __init__(self, ai_gateway: AIGateway, cache_manager: CacheManager, policy_evaluator: PolicyEvaluator = None, fact_ranker: FactRanker = None):
        self.ai = ai_gateway
        self.cache = cache_manager
        self.evaluator = policy_evaluator
        self.ranker = fact_ranker

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



    def create_plan(self, profile: CanonicalProfile, target: TargetContext, mock_ai: bool = False) -> ResumePlan:
        """
        Returns a ResumePlan dictating which projects and facts should be included.
        Does not mutate the CanonicalProfile.
        """
        planned_projects = []
        filtered_projects = self._filter_projects(profile.projects, target)
        
        # Build a new plan with the targeted data
        plan = ResumePlan(
            target=target,
            projects=[]
        )
        
        # Evaluate conditional policies FIRST, so FactRanker has access to the active priorities
        if self.evaluator:
            plan.policies = self.evaluator.evaluate(profile, target)
            
        # Now score facts using FactRanker and domain knowledge
        for proj in filtered_projects:
            if self.ranker:
                best_facts, status = self.ranker.rank_facts(proj, target, plan.policies, mock_ai=mock_ai)
            else:
                # Fallback if no ranker provided
                best_facts, status = proj.facts[:5], "fallback_unranked"
            
            planned_facts = [PlannedFact(fact_id=f.id, targeting_status=status) for f in best_facts]
            
            planned_proj = PlannedProject(
                project_id=proj.id,
                selected_facts=planned_facts
            )
            plan.projects.append(planned_proj)
            
        return plan
