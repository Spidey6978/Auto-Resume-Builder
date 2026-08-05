from typing import Dict, Type, Optional
from adapters.base import BaseAdapter

class AdapterRegistry:
    """
    Registry for resolving source_type strings to their respective adapter instances.
    """
    def __init__(self):
        self._adapters: Dict[str, BaseAdapter] = {}

    def register(self, source_type: str, adapter_instance: BaseAdapter) -> None:
        """Registers an initialized adapter instance for a given source type."""
        self._adapters[source_type] = adapter_instance

    def get_adapter(self, source_type: str) -> Optional[BaseAdapter]:
        """Retrieves the adapter instance for a given source type."""
        return self._adapters.get(source_type)

    def has_adapter(self, source_type: str) -> bool:
        return source_type in self._adapters
