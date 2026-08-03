import logging
from typing import Dict, Any, List
from src.models.domain import CanonicalProfile, TargetContext
from src.core.knowledge.store import KnowledgeStore
from src.core.knowledge.models import KnowledgeComponent, ConditionalPolicy
from src.models.plan import ResolvedPolicies

logger = logging.getLogger(__name__)

class CandidateState:
    """
    A view over the user's CanonicalProfile and TargetContext to provide boolean properties
    for evaluating conditional knowledge policies.
    """
    def __init__(self, profile: CanonicalProfile, target: TargetContext):
        self.profile = profile
        self.target = target
        
    @property
    def substantial_relevant_history(self) -> bool:
        """
        Determines if the candidate has enough history to warrant multiple pages.
        For now, a basic heuristic: 3 or more experiences, or 4 or more projects.
        """
        if len(self.profile.experience) >= 3:
            return True
        if len(self.profile.projects) >= 4:
            return True
        return False
        
    @property
    def has_publications(self) -> bool:
        """Checks if the candidate has awards/honors that look like publications."""
        for a in self.profile.awards:
            title = a.title.lower()
            if "paper" in title or "publication" in title or "journal" in title:
                return True
        return False

class PolicyEvaluator:
    """
    Resolves conflicting policies by following a strict hierarchy.
    """
    
    # The order of precedence (highest to lowest priority)
    HIERARCHY = [
        "document_type",
        "specialization",
        "domain",
        "career_stage",
        "global"
    ]
    
    def __init__(self, store: KnowledgeStore):
        self.store = store
        
    def _gather_components(self, target: TargetContext) -> List[KnowledgeComponent]:
        components = []
        
        # 1. document_type (Highest priority)
        if target.document_type:
            try:
                comp = self.store.get_component("document_type", target.document_type)
                if comp: components.append(comp)
            except ValueError:
                pass
                
        # 2. specialization
        if target.specialization:
            try:
                comp = self.store.get_component("specialization", target.specialization)
                if comp: components.append(comp)
            except ValueError:
                pass
                
        # 3. domain
        if target.domain:
            try:
                comp = self.store.get_component("domain", target.domain)
                if comp: components.append(comp)
            except ValueError:
                pass
                
        # 4. career_stage
        if target.career_stage:
            try:
                comp = self.store.get_component("career_stage", target.career_stage)
                if comp: components.append(comp)
            except ValueError:
                pass
                
        # 5. global (Lowest priority)
        try:
            # global directory can have multiple files
            global_comps = self.store.get_all_components("global")
            components.extend(global_comps.values())
        except ValueError:
            pass
            
        return components

    def _evaluate_policy(self, policy: ConditionalPolicy, state: CandidateState) -> Dict[str, Any]:
        """Evaluates conditions against the candidate state and returns the winning recommendation."""
        for condition in policy.conditions:
            cond_name = condition.condition
            # Check if this condition is a known boolean property on CandidateState
            if hasattr(state, cond_name):
                # We expect the property to be callable or a standard property
                prop_val = getattr(state, cond_name)
                # If it's a method, call it. If it's a @property, just check truthiness.
                if callable(prop_val):
                    if prop_val():
                        return condition.recommendation
                else:
                    if prop_val:
                        return condition.recommendation
            else:
                logger.warning(f"Unknown condition '{cond_name}' in policy '{policy.id}'. Skipping.")
                
        # Fallback to the base recommendation if no conditions match
        return policy.recommendation

    def evaluate(self, profile: CanonicalProfile, target: TargetContext) -> ResolvedPolicies:
        state = CandidateState(profile, target)
        components = self._gather_components(target)
        
        resolved = ResolvedPolicies()
        
        # Track which category resolved which policy, to enforce hierarchy
        resolved_policy_sources = {} 
        
        for comp in components:
            comp_level_index = self.HIERARCHY.index(comp.type.value)
            
            # Resolve generic policies
            for policy in comp.policies:
                existing_source_index = resolved_policy_sources.get(policy.id)
                # If this policy hasn't been resolved yet, OR if this component is HIGHER priority (lower index)
                if existing_source_index is None or comp_level_index < existing_source_index:
                    resolved.policies[policy.id] = self._evaluate_policy(policy, state)
                    resolved_policy_sources[policy.id] = comp_level_index
                    
            # For priorities, we union them ordered by hierarchy (specific first).
            for priority in comp.priorities:
                # To prevent duplicates if the same priority ID is defined in multiple places:
                if not any(p["id"] == priority.id for p in resolved.active_priorities):
                    resolved.active_priorities.append(priority.model_dump())
                    
        return resolved
