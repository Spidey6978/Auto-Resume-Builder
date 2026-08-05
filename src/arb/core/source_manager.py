import os
import yaml
import logging
from pathlib import Path
from typing import Optional, List

from arb.models.domain import SourceRecord, SourceRegistryModel
from arb.core.paths import get_user_data_dir

logger = logging.getLogger(__name__)

class SourceManager:
    """
    Manages persistence of SourceRecord data.
    Provides atomic read/write to sources.yaml in the user data directory.
    """
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or get_user_data_dir()
        self.sources_path = self.data_dir / "sources.yaml"
        self.registry = self.load()

    def load(self) -> SourceRegistryModel:
        """Loads the registry from sources.yaml, creating it if it doesn't exist."""
        if not self.sources_path.exists():
            return SourceRegistryModel()
            
        try:
            with open(self.sources_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                
            if not data:
                return SourceRegistryModel()
                
            return SourceRegistryModel.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load sources from {self.sources_path}: {e}")
            return SourceRegistryModel()

    def save(self):
        """Atomically saves the registry to sources.yaml."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        temp_path = self.sources_path.with_suffix(".yaml.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.dump(self.registry.to_dict(), f, sort_keys=False, default_flow_style=False)
            temp_path.replace(self.sources_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to save sources to {self.sources_path}: {e}")

    def get_source(self, id: str) -> Optional[SourceRecord]:
        """Fetch a source by its ID."""
        for src in self.registry.sources:
            if src.id == id:
                return src
        return None

    def upsert_source(self, record: SourceRecord):
        """Insert or update a source record."""
        for i, src in enumerate(self.registry.sources):
            if src.id == record.id:
                self.registry.sources[i] = record
                return
        self.registry.sources.append(record)

    def list_sources(self) -> List[SourceRecord]:
        """Return all sources in the registry."""
        return self.registry.sources
