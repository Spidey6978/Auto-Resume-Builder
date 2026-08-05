import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from arb.models.domain import EvidenceItem, Project, ExperienceItem, EducationItem, AwardItem
from arb.core.ai_gateway import AIGateway
from arb.core.cache import CacheManager
from arb.core.fact_extractor import FactExtractor

logger = logging.getLogger(__name__)

@dataclass
class EntityExtractionResult:
    projects: List[Project] = field(default_factory=list)
    experience: List[ExperienceItem] = field(default_factory=list)
    education: List[EducationItem] = field(default_factory=list)
    awards: List[AwardItem] = field(default_factory=list)
    skills: Dict[str, List[str]] = field(default_factory=dict)

class EvidenceExtractor:
    """
    Takes semantically typed EvidenceItems (e.g. kind="experience_block") 
    and translates them into structured Canonical entities with provenance.
    Leaves fact-extraction responsibilities to the FactExtractor.
    """
    CACHE_NAMESPACE = "llm_entities"

    def __init__(self, ai_gateway: AIGateway, cache_manager: CacheManager, fact_extractor: FactExtractor):
        self.ai = ai_gateway
        self.cache = cache_manager
        self.fact_extractor = fact_extractor

    def _clean_json_response(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    def extract(self, evidence: EvidenceItem, mock_ai: bool = False) -> EntityExtractionResult:
        result = EntityExtractionResult()
        
        kind = evidence.kind
        if kind == "experience_block":
            result.experience = self._extract_experience(evidence, mock_ai)
        elif kind == "education_block":
            result.education = self._extract_education(evidence, mock_ai)
        elif kind == "projects_block":
            result.projects = self._extract_projects(evidence, mock_ai)
        elif kind == "awards_block":
            result.awards = self._extract_awards(evidence, mock_ai)
        elif kind == "skills_block":
            result.skills = self._extract_skills(evidence, mock_ai)
            
        # Deterministic extractions (from structured adapters like Manual or LinkedIn)
        elif kind == "experience":
            result.experience = self._extract_deterministic_experience(evidence)
        elif kind == "projects":
            result.projects = self._extract_deterministic_project(evidence)
        elif kind == "education":
            result.education = self._extract_deterministic_education(evidence)
        elif kind == "awards":
            result.awards = self._extract_deterministic_award(evidence)
        elif kind == "skills":
            # Just extract it as a dict mapping categories to lists of strings
            result.skills = evidence.content
            
        return result
        
    def _extract_deterministic_experience(self, evidence: EvidenceItem) -> List[ExperienceItem]:
        data = evidence.content.copy()
        data["id"] = data.get("id", f"{data.get('organization', '')}_{data.get('title', '')}".replace(" ", "_").lower())
        if not data["id"]:
            data["id"] = evidence.id
        return [ExperienceItem.from_dict(data)]

    def _extract_deterministic_project(self, evidence: EvidenceItem) -> List[Project]:
        data = evidence.content.copy()
        data["id"] = data.get("id", data.get("name", "").replace(" ", "_").lower())
        if not data["id"]:
            data["id"] = evidence.id
        return [Project.from_dict(data)]

    def _extract_deterministic_education(self, evidence: EvidenceItem) -> List[EducationItem]:
        data = evidence.content.copy()
        data["id"] = data.get("id", f"{data.get('institution', '')}_{data.get('degree', '')}".replace(" ", "_").lower())
        if not data["id"]:
            data["id"] = evidence.id
        return [EducationItem.from_dict(data)]

    def _extract_deterministic_award(self, evidence: EvidenceItem) -> List[AwardItem]:
        data = evidence.content.copy()
        data["id"] = data.get("id", data.get("title", "").replace(" ", "_").lower())
        if not data["id"]:
            data["id"] = evidence.id
        return [AwardItem.from_dict(data)]
        
    def _extract_experience(self, evidence: EvidenceItem, mock_ai: bool) -> List[ExperienceItem]:
        prompt = f"""
        Extract professional experience records from the following text.
        Return ONLY a JSON array of objects with schema:
        [
          {{
            "id": "normalized_company_title",
            "organization": "Company Name",
            "title": "Job Title",
            "location": "City, State",
            "start_date": "YYYY-MM",
            "end_date": "YYYY-MM or Present"
          }}
        ]
        
        TEXT:
        {evidence.content}
        """
        response = self.ai.generate_text(prompt, mock_ai=mock_ai)
        try:
            data = json.loads(self._clean_json_response(response))
            return [ExperienceItem.from_dict(d) for d in data]
        except Exception:
            return []

    def _extract_education(self, evidence: EvidenceItem, mock_ai: bool) -> List[EducationItem]:
        prompt = f"""
        Extract education records from the following text.
        Return ONLY a JSON array of objects with schema:
        [
          {{
            "id": "normalized_school_degree",
            "institution": "University Name",
            "degree": "Degree Level and Major",
            "location": "City, State",
            "start_date": "YYYY-MM",
            "end_date": "YYYY-MM or Expected YYYY-MM"
          }}
        ]
        
        TEXT:
        {evidence.content}
        """
        response = self.ai.generate_text(prompt, mock_ai=mock_ai)
        try:
            data = json.loads(self._clean_json_response(response))
            return [EducationItem.from_dict(d) for d in data]
        except Exception:
            return []

    def _extract_projects(self, evidence: EvidenceItem, mock_ai: bool) -> List[Project]:
        prompt = f"""
        Extract project records from the following text.
        Return ONLY a JSON array of objects with schema:
        [
          {{
            "id": "normalized_project_name",
            "name": "Project Name",
            "link": "URL if present",
            "tech_stack": ["Tech1", "Tech2"]
          }}
        ]
        
        TEXT:
        {evidence.content}
        """
        response = self.ai.generate_text(prompt, mock_ai=mock_ai)
        try:
            data = json.loads(self._clean_json_response(response))
            return [Project.from_dict(d) for d in data]
        except Exception:
            return []

    def _extract_awards(self, evidence: EvidenceItem, mock_ai: bool) -> List[AwardItem]:
        prompt = f"""
        Extract awards/honors from the following text.
        Return ONLY a JSON array of objects with schema:
        [
          {{
            "id": "normalized_award_name",
            "title": "Award Name",
            "organization": "Issuing Org",
            "year": 2023
          }}
        ]
        
        TEXT:
        {evidence.content}
        """
        response = self.ai.generate_text(prompt, mock_ai=mock_ai)
        try:
            data = json.loads(self._clean_json_response(response))
            return [AwardItem.from_dict(d) for d in data]
        except Exception:
            return []

    def _extract_skills(self, evidence: EvidenceItem, mock_ai: bool) -> Dict[str, List[str]]:
        prompt = f"""
        Extract skills from the following text and categorize them.
        Return ONLY a JSON object with category keys (e.g. "Languages", "Frameworks") and lists of strings as values.
        
        TEXT:
        {evidence.content}
        """
        response = self.ai.generate_text(prompt, mock_ai=mock_ai)
        try:
            return json.loads(self._clean_json_response(response))
        except Exception:
            return {}
