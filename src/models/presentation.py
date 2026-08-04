from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from models.domain import PersonalInfo, EducationItem

@dataclass
class RenderedBullet:
    text: str
    source_fact_ids: List[str] = field(default_factory=list)
    relevance_score: float = 0.0


@dataclass
class RenderedProject:
    id: str
    name: str
    link: Optional[str]
    tech_stack: List[str]
    bullets: List[RenderedBullet]


@dataclass
class RenderedExperience:
    id: str
    organization: str
    title: str
    location: Optional[str]
    start_date: str
    end_date: Optional[str]
    bullets: List[RenderedBullet]


@dataclass
class RenderedAward:
    id: str
    title: str
    event: Optional[str]
    organization: Optional[str]
    year: Optional[int]
    bullets: List[str]


@dataclass
class ResumeDocument:
    """The complete presentation model passed directly to the Compiler."""
    personal: PersonalInfo
    education: List[EducationItem]
    experience: List[RenderedExperience]
    awards: List[RenderedAward]
    projects: List[RenderedProject]
    skills: Dict[str, List[str]]
    section_order: List[str] = field(default_factory=list)
    page_policy: Dict[str, Any] = field(default_factory=dict)
