from abc import ABC, abstractmethod
from typing import Any, Dict
from arb.models.domain import SourceResult

class BaseAdapter(ABC):
    """
    Abstract base class for all data source adapters.
    """

    @abstractmethod
    def ingest(self, identifier: str, **kwargs) -> SourceResult:
        """Fetches data from source and returns a standardized SourceResult containing EvidenceItems."""
        pass
