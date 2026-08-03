from enum import Enum
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

class PolicyStrength(str, Enum):
    ABSOLUTE_REQUIREMENT = "absolute_requirement"
    STRONG_RECOMMENDATION = "strong_recommendation"
    WEAK_RECOMMENDATION = "weak_recommendation"
    ADVISORY = "advisory"

class EvidenceRef(BaseModel):
    title: str
    publisher: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    source_type: Optional[str] = None

class RecommendationCondition(BaseModel):
    condition: str
    recommendation: Dict[str, Any]
    evidence_refs: List[str] = Field(default_factory=list)

class ConditionalPolicy(BaseModel):
    id: str
    recommendation: Dict[str, Any]
    strength: PolicyStrength = PolicyStrength.STRONG_RECOMMENDATION
    conditions: List[RecommendationCondition] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)

class DisputedPosition(BaseModel):
    recommendation: Dict[str, Any]
    evidence_refs: List[str] = Field(default_factory=list)

class DisputedGuidance(BaseModel):
    id: str
    positions: List[DisputedPosition] = Field(default_factory=list)

class Priority(BaseModel):
    id: str
    description: Optional[str] = None
    importance: str
    evidence_refs: List[str] = Field(default_factory=list)

class KnowledgeComponent(BaseModel):
    """
    Base model for any YAML file in the KnowledgeStore 
    (Global, Domain, Specialization, Career Stage, Document Type)
    """
    schema_version: str = "1.0"
    id: str
    type: str # 'global', 'domain', 'specialization', 'career_stage', 'document_type', 'geography'
    
    # Generic policies (e.g. page_policy, section_order, etc)
    policies: List[ConditionalPolicy] = Field(default_factory=list)
    
    # Hiring priorities (what matters in this domain/role)
    priorities: List[Priority] = Field(default_factory=list)
    
    # Disputed or conflicting advice
    disputed_guidance: List[DisputedGuidance] = Field(default_factory=list)
    
    # Raw source metadata referenced by evidence_refs
    sources: Dict[str, EvidenceRef] = Field(default_factory=dict)
