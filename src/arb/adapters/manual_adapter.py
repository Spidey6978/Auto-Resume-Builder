import json
import uuid
import datetime
from typing import Dict, Any, List

from arb.models.domain import SourceResult, SourceStatus, EvidenceItem, SourceRef
from arb.adapters.base import BaseAdapter

class ManualAdapter(BaseAdapter):
    """
    Adapter for manually entering career facts via interactive CLI prompts.
    Produces highly structured EvidenceItems tagged with 'manual' provenance.
    """

    def __init__(self):
        pass

    def ingest(self, identifier: str) -> SourceResult:
        """
        identifier is a JSON string representing the payload.
        Expected format:
        {
            "entity_type": "experience|project|education|award",
            "data": { ... }
        }
        """
        try:
            payload = json.loads(identifier)
        except json.JSONDecodeError:
            return SourceResult(
                source_type="manual",
                source_id="manual:cli",
                status=SourceStatus.FAILED,
                metadata={"error": "Identifier must be a valid JSON payload for manual adapter."}
            )
            
        entity_type = payload.get("entity_type", "").lower()
        supported = ["experience", "project", "education", "award"]
        
        if entity_type not in supported:
            return SourceResult(
                source_type="manual",
                source_id="manual:cli",
                status=SourceStatus.FAILED,
                metadata={"error": f"Unsupported manual entity type '{entity_type}'. Must be one of: {', '.join(supported)}"}
            )
            
        data = payload.get("data", {})
        if not data:
            return SourceResult(
                source_type="manual",
                source_id="manual:cli",
                status=SourceStatus.FAILED,
                metadata={"error": "Empty data payload."}
            )
            
        # Create a unique ID for this manual entry
        entry_id = f"manual_{uuid.uuid4().hex[:8]}"
        
        # We can format facts if they are passed as strings
        if "facts" in data and isinstance(data["facts"], list):
            formatted_facts = []
            for f in data["facts"]:
                if isinstance(f, str):
                    formatted_facts.append({
                        "id": f"fact_{uuid.uuid4().hex[:8]}",
                        "text": f,
                        "fact_type": "general",
                        "source_refs": [{"type": "manual", "id": "manual:cli"}]
                    })
                elif isinstance(f, dict):
                    formatted_facts.append(f)
            data["facts"] = formatted_facts
        
        evidence = EvidenceItem(
            id=entry_id,
            kind=entity_type,
            content=data,
            provenance=SourceRef(type="manual", id="manual:cli")
        )
        
        return SourceResult(
            source_type="manual",
            source_id="manual:cli",
            evidence=[evidence],
            status=SourceStatus.SUCCESS,
            metadata={"entity_type": entity_type, "name": "Manual CLI Entry"}
        )

    def _prompt_experience(self) -> Dict[str, Any]:
        org = input("Organization/Company: ").strip()

