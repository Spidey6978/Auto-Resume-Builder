from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from src.models.domain import TargetContext

@dataclass
class PlannedFact:
    fact_id: str
    targeting_status: Optional[str] = None  # e.g., "success", "cache_hit", "fallback_unranked"

@dataclass
class PlannedProject:
    project_id: str
    selected_facts: List[PlannedFact]

@dataclass
class PlannedExperience:
    experience_id: str
    selected_facts: List[PlannedFact]

@dataclass
class ResolvedPolicies:
    # This will be populated in Milestone 3.3 when we implement the PolicyEvaluator
    page_policy: Dict[str, Any] = field(default_factory=dict)
    section_order: List[str] = field(default_factory=list)
    active_priorities: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ResumePlan:
    """The blueprint for generating a specific targeted resume."""
    target: TargetContext
    projects: List[PlannedProject] = field(default_factory=list)
    experience: List[PlannedExperience] = field(default_factory=list)
    policies: ResolvedPolicies = field(default_factory=ResolvedPolicies)
