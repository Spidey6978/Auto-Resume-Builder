from dataclasses import dataclass, field
from typing import List, Dict, Literal
import yaml

@dataclass
class TypedSourceRef:
    adapter: str
    priority: Literal["primary", "optional"]
    guidance: str

@dataclass
class EntityVisibility:
    primary: List[str]
    optional: List[str]

@dataclass
class DomainConfig:
    id: str
    display_name: str
    suggested_sources: List[TypedSourceRef]
    profile_entities: EntityVisibility
    default_document_type: str

    @classmethod
    def from_yaml(cls, path: str) -> "DomainConfig":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        sources = [TypedSourceRef(**s) for s in data.get("suggested_sources", [])]
        entities = EntityVisibility(**data.get("profile_entities", {"primary": [], "optional": []}))
        
        return cls(
            id=data["id"],
            display_name=data["display_name"],
            suggested_sources=sources,
            profile_entities=entities,
            default_document_type=data["default_document_type"]
        )
