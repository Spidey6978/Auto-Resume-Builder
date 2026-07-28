from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAdapter(ABC):
    """
    Abstract base class for all data source adapters.
    """

    @abstractmethod
    def fetch(self, **kwargs) -> Dict[str, Any]:
        """Fetches data from source and returns a standardized data payload."""
        pass
