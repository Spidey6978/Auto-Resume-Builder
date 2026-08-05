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
from core.domain_loader import DomainLoader

logger = logging.getLogger(__name__)

class TargetEngine:
    """
    Core engine for applying a TargetContext to a CanonicalProfile.
    Scores and filters facts/projects based on the target description.
    """
    CACHE_NAMESPACE = "llm_fact_scoring"
    PROMPT_VERSION = "scoring-v1.0"

    def __init__(self, ai_gateway: AIGateway, cache_manager: CacheManager, policy_evaluator: PolicyEvaluator = None, fact_ranker: FactRanker = None, domain_loader: DomainLoader = None):
        self.ai = ai_gateway
        self.cache = cache_manager
        self.evaluator = policy_evaluator
        self.ranker = fact_ranker
        self.domain_loader = domain_loader

    def _filter_projects(self, projects: List[Project], target: TargetContext) -> List[Project]:
        # Check domain config for entity visibility
        if self.domain_loader and target.domain_id:
            domain_config = self.domain_loader.get_domain(target.domain_id)
            if domain_config:
                allowed_entities = domain_config.profile_entities.primary + domain_config.profile_entities.optional
                if "projects" not in allowed_entities:
                    logger.info(f"TargetEngine: Masking all projects. 'projects' not in allowed entities for domain '{target.domain_id}'.")
                    return []

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
                scored_facts, status = self.ranker.rank_facts(proj, target, plan.policies, mock_ai=mock_ai)
            else:
                from core.fact_ranker import ScoredFact
                # Fallback if no ranker provided
                scored_facts, status = [ScoredFact(fact=f, score=0.0, reasons=["fallback_unranked"]) for f in proj.facts[:5]], "fallback_unranked"
            
            planned_facts = [
                PlannedFact(
                    fact_id=sf.fact.id, 
                    relevance_score=sf.score, 
                    reasons=sf.reasons, 
                    targeting_status=status
                ) for sf in scored_facts
            ]
            
            planned_proj = PlannedProject(
                project_id=proj.id,
                selected_facts=planned_facts
            )
            plan.projects.append(planned_proj)
            
        return plan
