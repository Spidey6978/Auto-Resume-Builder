from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class ProjectItem:
    name: str
    tech_stack: str
    link: str
    bullets: List[str] = field(default_factory=list)
    readme_content: Optional[str] = None


@dataclass
class ProfileData:
    github_username: Optional[str] = None
    name: str = ""
    phone: str = ""
    email: str = ""
    github: str = ""
    linkedin: str = ""
    location: str = ""
    summary: str = ""
    education: List[Dict[str, Any]] = field(default_factory=list)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    awards: List[Dict[str, Any]] = field(default_factory=list)
    technical_skills: Dict[str, str] = field(default_factory=dict)
    projects: List[ProjectItem] = field(default_factory=list)
