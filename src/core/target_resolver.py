import json
import logging
from typing import Optional, List
from src.models.domain import TargetContext, TargetRule
from src.core.ai_gateway import AIGateway
from src.core.knowledge.store import KnowledgeStore

logger = logging.getLogger(__name__)

class JobDescriptionExtractor:
    def __init__(self, ai_gateway: AIGateway):
        self.ai = ai_gateway
        
    def extract(self, jd_text: str, valid_domains: List[str], valid_specializations: List[str], valid_career_stages: List[str], mock_ai: bool = False) -> dict:
        """
        Parses a raw job description and extracts semantic fields using the LLM.
        Forces the LLM to snap to valid knowledge categories where possible.
        """
        prompt = f"""
        You are an expert technical recruiter analyzing a job description.
        Extract the following information from the text and return it as a pure JSON object.
        
        Job Description:
        ---
        {jd_text}
        ---
        
        Valid Domains: {valid_domains}
        Valid Specializations: {valid_specializations}
        Valid Career Stages: {valid_career_stages}
        
        Rules:
        - Map "domain" to ONE of the Valid Domains, or null if it doesn't fit any.
        - Map "specialization" to ONE of the Valid Specializations, or null.
        - Map "career_stage" to ONE of the Valid Career Stages, or null.
        - Extract a list of up to 10 "hard_skills" (e.g. programming languages, tools, frameworks) strictly required or strongly preferred.
        - Extract a list of up to 5 "implied_traits" (e.g. "fast-paced", "cross-functional", "research-heavy").
        
        Output format:
        {{
            "domain": "string or null",
            "specialization": "string or null",
            "career_stage": "string or null",
            "hard_skills": ["skill1", "skill2"],
            "implied_traits": ["trait1", "trait2"]
        }}
        """
        
        if mock_ai:
            return {
                "domain": valid_domains[0] if valid_domains else None,
                "specialization": valid_specializations[0] if valid_specializations else None,
                "career_stage": valid_career_stages[0] if valid_career_stages else None,
                "hard_skills": ["python", "aws"],
                "implied_traits": ["fast-paced"]
            }
            
        try:
            response_text = self.ai.generate_text(prompt, mock_ai=mock_ai)
            
            # Find JSON boundaries
            json_start = response_text.find("{")
            json_end = response_text.rfind("}")
            
            if json_start != -1 and json_end != -1:
                return json.loads(response_text[json_start:json_end+1])
            return {}
        except Exception as e:
            logger.error(f"Failed to extract JD info: {e}")
            return {}

class TargetResolver:
    """
    Constructs a complete TargetContext from user input and LLM extraction.
    """
    def __init__(self, extractor: JobDescriptionExtractor, knowledge_store: KnowledgeStore):
        self.extractor = extractor
        self.knowledge_store = knowledge_store
        
    def resolve(self, target_id: str, raw_description: str, project_rules: TargetRule = None, experience_rules: TargetRule = None, mock_ai: bool = False) -> TargetContext:
        """
        Resolves a raw job description into a semantic TargetContext.
        """
        # 1. Fetch valid knowledge categories
        valid_domains = list(self.knowledge_store.get_all_components("domain").keys())
        valid_specializations = list(self.knowledge_store.get_all_components("specialization").keys())
        valid_career_stages = list(self.knowledge_store.get_all_components("career_stage").keys())
        
        # 2. Extract semantic fields via LLM
        extracted = self.extractor.extract(
            jd_text=raw_description,
            valid_domains=valid_domains,
            valid_specializations=valid_specializations,
            valid_career_stages=valid_career_stages,
            mock_ai=mock_ai
        )
        
        # 3. Construct TargetContext
        return TargetContext(
            id=target_id,
            description=raw_description,
            domain=extracted.get("domain"),
            specialization=extracted.get("specialization"),
            career_stage=extracted.get("career_stage"),
            hard_skills=extracted.get("hard_skills", []),
            implied_traits=extracted.get("implied_traits", []),
            project_rules=project_rules or TargetRule(),
            experience_rules=experience_rules or TargetRule()
        )
