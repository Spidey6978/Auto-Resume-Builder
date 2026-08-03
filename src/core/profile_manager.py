import os
import yaml
import logging
from typing import Dict, Any, List, Optional
from models.domain import CanonicalProfile, Project, Fact
from core.fact_extractor import ExtractionResult, ExtractionStatus

logger = logging.getLogger(__name__)

class ProfileManager:
    """
    Owns canonical-profile loading, merging, and atomic persistence.
    Safely bridges machine-ingested data with human-editable YAML.
    """
    
    def __init__(self, yaml_path: str):
        self.yaml_path = yaml_path
        self.profile = self._load()
        
    def _load(self) -> CanonicalProfile:
        if os.path.exists(self.yaml_path):
            try:
                return CanonicalProfile.from_yaml(self.yaml_path)
            except Exception as e:
                raise RuntimeError(
                    f"CRITICAL: Failed to parse existing canonical profile at '{self.yaml_path}'. "
                    f"Please fix any YAML formatting errors manually. "
                    f"Aborting to prevent overwriting your data. Error: {e}"
                )
        return CanonicalProfile()

    def save(self) -> None:
        """
        Atomically saves the canonical profile to prevent corruption if serialization fails mid-write.
        """
        tmp_path = f"{self.yaml_path}.tmp"
        try:
            self.profile.to_yaml(tmp_path)
            os.replace(tmp_path, self.yaml_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise RuntimeError(f"Failed to save profile: {e}")

    def upsert_project(self, source_id: str, raw_name: str, link: Optional[str], normalized_languages: List[str], extraction_result: ExtractionResult) -> None:
        """
        Merges ingested project data into the canonical profile.
        - Preserves human-edited fields (category, name, link).
        - Merges tech stack while preserving order.
        - Replaces facts matching the source_id without deleting manual facts, ONLY if extraction succeeded.
        """
        # Find existing project by canonical source_id
        existing_project = None
        for proj in self.profile.projects:
            if proj.id == source_id:
                existing_project = proj
                break
                
        if not existing_project:
            # 1. New Project -> Initialize entity
            new_project = Project(
                id=source_id,
                name=raw_name,
                link=link,
                tech_stack=normalized_languages,
                category=[],
                facts=extraction_result.facts if extraction_result.status in (ExtractionStatus.SUCCESS, ExtractionStatus.NO_FACTS) else []
            )
            self.profile.projects.append(new_project)
            return

        # 2. Existing Project -> Preserve human fields, merge arrays safely
        
        # Order-preserving tech stack merge
        # dict.fromkeys() retains insertion order and drops duplicates.
        existing_project.tech_stack = list(dict.fromkeys(existing_project.tech_stack + normalized_languages))
        
        # Fact Provenance Replacement
        if extraction_result.status in (ExtractionStatus.SUCCESS, ExtractionStatus.NO_FACTS):
            preserved_facts = []
            
            for fact in existing_project.facts:
                # Remove THIS source's claim from the fact's provenance
                if source_id in fact.source_refs:
                    fact.source_refs.remove(source_id)
                
                # If the fact still has remaining provenance (e.g., 'manual' or another source), preserve it!
                if fact.source_refs:
                    preserved_facts.append(fact)
                    
            # Append freshly extracted facts
            existing_project.facts = preserved_facts + extraction_result.facts

        # Note: If extraction_result.status is AI_ERROR or INVALID_RESPONSE, 
        # existing_project.facts remains completely untouched. Data is preserved!
