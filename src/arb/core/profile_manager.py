import os
import yaml
import logging
from arb.models.domain import CanonicalProfile

logger = logging.getLogger(__name__)

class ProfileManager:
    """
    Owns canonical-profile loading and atomic persistence.
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

    def upsert_project(self, source_id: str, raw_name: str, link: str = None, normalized_languages: list = None, extraction_result = None) -> None:
        """
        Upserts a project and its extracted facts into the canonical profile.
        Safely bridges with ProfileMerger and saves atomically.
        """
        from arb.models.domain import Project
        from arb.core.profile_merger import ProfileMerger
        from arb.core.evidence_extractor import EntityExtractionResult
        from arb.core.fact_extractor import ExtractionStatus

        if extraction_result is not None:
            if hasattr(extraction_result, "status") and extraction_result.status != ExtractionStatus.SUCCESS:
                logger.warning("Extraction result status indicates failure; skipping upsert_project to avoid corruption.")
                return

        facts = getattr(extraction_result, "facts", []) if extraction_result else []
        incoming_proj = Project(
            id=source_id,
            name=raw_name,
            link=link,
            tech_stack=normalized_languages or [],
            facts=facts
        )
        merger = ProfileMerger(self.profile)
        merger.merge(EntityExtractionResult(projects=[incoming_proj]))
        self.save()
