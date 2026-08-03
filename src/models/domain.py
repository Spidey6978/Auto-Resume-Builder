import yaml
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any


class SourceStatus(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"
    FAILED = "failed"


@dataclass
class Fact:
    """Atomic evidence unit for projects, experience, or awards."""
    id: str
    text: str
    fact_type: str  # e.g., "implementation", "performance", "math_physics", "leadership"
    metric: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    source_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fact":
        return cls(
            id=data["id"],
            text=data["text"],
            fact_type=data.get("fact_type", "general"),
            metric=data.get("metric"),
            tags=data.get("tags", []),
            source_refs=data.get("source_refs", [])
        )


@dataclass
class Project:
    """Project entity representing a technical effort."""
    id: str
    name: str
    link: Optional[str] = None
    tech_stack: List[str] = field(default_factory=list)
    category: List[str] = field(default_factory=list)
    facts: List[Fact] = field(default_factory=list)
    targeting_status: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["facts"] = [f.to_dict() for f in self.facts]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        facts_data = data.get("facts", [])
        facts = [Fact.from_dict(f) if isinstance(f, dict) else f for f in facts_data]
        return cls(
            id=data["id"],
            name=data["name"],
            link=data.get("link"),
            tech_stack=data.get("tech_stack", []),
            category=data.get("category", []) if isinstance(data.get("category"), list) else ([data["category"]] if data.get("category") else []),
            facts=facts,
            targeting_status=data.get("targeting_status")
        )


@dataclass
class ExperienceItem:
    """Work history or leadership position entity."""
    id: str
    organization: str
    title: str
    location: Optional[str] = None
    start_date: str = ""
    end_date: Optional[str] = None
    facts: List[Fact] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["facts"] = [f.to_dict() for f in self.facts]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperienceItem":
        facts_data = data.get("facts", [])
        facts = [Fact.from_dict(f) if isinstance(f, dict) else f for f in facts_data]
        return cls(
            id=data["id"],
            organization=data.get("organization", data.get("company", "")),
            title=data["title"],
            location=data.get("location"),
            start_date=data.get("start_date", data.get("dates", "")),
            end_date=data.get("end_date"),
            facts=facts
        )


@dataclass
class AwardItem:
    """Honor, award, or competition victory entity."""
    id: str
    title: str
    event: Optional[str] = None
    organization: Optional[str] = None
    year: Optional[int] = None
    facts: List[Fact] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["facts"] = [f.to_dict() for f in self.facts]
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AwardItem":
        facts_data = data.get("facts", [])
        facts = [Fact.from_dict(f) if isinstance(f, dict) else f for f in facts_data]
        raw_year = data.get("year")
        year_val = int(raw_year) if raw_year is not None and str(raw_year).isdigit() else None
        return cls(
            id=data["id"],
            title=data["title"],
            event=data.get("event"),
            organization=data.get("organization"),
            year=year_val,
            facts=facts
        )


@dataclass
class EducationItem:
    """Education history entity."""
    id: str
    institution: str
    degree: str
    field: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EducationItem":
        return cls(
            id=data.get("id", data.get("school", "edu_item")),
            institution=data.get("institution", data.get("school", "")),
            degree=data["degree"],
            field=data.get("field"),
            location=data.get("location"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date", data.get("dates"))
        )


@dataclass
class PersonalInfo:
    """Contact details and links for header rendering."""
    name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    github: Optional[str] = None
    linkedin: Optional[str] = None
    website: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalInfo":
        return cls(
            name=data.get("name", ""),
            email=data.get("email"),
            phone=data.get("phone"),
            location=data.get("location"),
            github=data.get("github"),
            linkedin=data.get("linkedin"),
            website=data.get("website")
        )


@dataclass
class SourceResult:
    """Raw data payload ingested by a source adapter prior to fact extraction."""
    source_id: str
    source_type: str
    raw_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: SourceStatus = SourceStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class TargetRule:
    exclude: List[str] = field(default_factory=list)
    include_only: List[str] = field(default_factory=list)

@dataclass
class TargetContext:
    id: str
    description: str # The raw Job Description text or a general goal
    
    # Semantic fields extracted from JD (populated by TargetResolver)
    domain: Optional[str] = None
    specialization: Optional[str] = None
    career_stage: Optional[str] = None
    hard_skills: List[str] = field(default_factory=list)
    implied_traits: List[str] = field(default_factory=list)
    
    # Explicit rules
    project_rules: TargetRule = field(default_factory=TargetRule)
    experience_rules: TargetRule = field(default_factory=TargetRule)



@dataclass
class CanonicalProfile:
    """
    Top-level domain model representing a user's canonical professional knowledge.
    Contains versioning, personal info, education, awards, experience, projects, and skills.
    """
    schema_version: int = 1
    personal: PersonalInfo = field(default_factory=PersonalInfo)
    education: List[EducationItem] = field(default_factory=list)
    experience: List[ExperienceItem] = field(default_factory=list)
    awards: List[AwardItem] = field(default_factory=list)
    projects: List[Project] = field(default_factory=list)
    skills: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "personal": self.personal.to_dict(),
            "education": [e.to_dict() for e in self.education],
            "experience": [e.to_dict() for e in self.experience],
            "awards": [a.to_dict() for a in self.awards],
            "projects": [p.to_dict() for p in self.projects],
            "skills": self.skills
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalProfile":
        personal = PersonalInfo.from_dict(data.get("personal", {})) if "personal" in data else PersonalInfo.from_dict(data)
        education = [EducationItem.from_dict(e) for e in data.get("education", [])]
        experience = [ExperienceItem.from_dict(e) for e in data.get("experience", [])]
        awards = [AwardItem.from_dict(a) for a in data.get("awards", [])]
        projects = [Project.from_dict(p) for p in data.get("projects", [])]
        skills = data.get("skills", data.get("technical_skills", {}))

        # Normalize skills dict values to lists if they are stored as comma-separated strings
        normalized_skills = {}
        if isinstance(skills, dict):
            for cat, items in skills.items():
                if isinstance(items, str):
                    normalized_skills[cat] = [i.strip() for i in items.split(",") if i.strip()]
                elif isinstance(items, list):
                    normalized_skills[cat] = items

        return cls(
            schema_version=data.get("schema_version", 1),
            personal=personal,
            education=education,
            experience=experience,
            awards=awards,
            projects=projects,
            skills=normalized_skills
        )

    def to_yaml(self, path: str) -> None:
        """Serializes CanonicalProfile to a YAML file."""
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, sort_keys=False, default_flow_style=False)

    @classmethod
    def from_yaml(cls, path: str) -> "CanonicalProfile":
        """Loads a CanonicalProfile from a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)
