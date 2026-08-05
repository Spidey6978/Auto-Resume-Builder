import os
import yaml
from typing import Dict, Optional
from pathlib import Path
from arb.core.knowledge.models import (
    KnowledgeComponent
)

class KnowledgeStore:
    def __init__(self, knowledge_dir: str):
        self.knowledge_dir = Path(knowledge_dir)
        self._components: Dict[str, Dict[str, KnowledgeComponent]] = {
            "global": {},
            "domain": {},
            "specialization": {},
            "career_stage": {},
            "document_type": {},
            "geography": {}
        }
        self._dir_mapping = {
            "global": "global",
            "domain": "domains",
            "specialization": "specializations",
            "career_stage": "career_stages",
            "document_type": "document_types",
            "geography": "geography"
        }
        self.load_all()

    def load_all(self):
        if not self.knowledge_dir.exists():
            return

        for category, dir_name in self._dir_mapping.items():
            category_dir = self.knowledge_dir / dir_name
            if not category_dir.exists():
                continue
                
            for filename in os.listdir(category_dir):
                if filename.endswith(('.yaml', '.yml')):
                    filepath = category_dir / filename
                    self._load_file(category, filepath)

    def _load_file(self, category: str, filepath: Path):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        if not data:
            return
            
        component = KnowledgeComponent(**data)
        
        # Verify type matches the directory it's in
        if component.type.value != category:
            raise ValueError(f"Component type '{component.type.value}' does not match directory category '{category}' in {filepath}")
            
        self._validate_evidence_refs(component, filepath)
            
        self._components[category][component.id] = component

    def _validate_evidence_refs(self, component: KnowledgeComponent, filepath: Path):
        valid_refs = set(component.sources.keys())
        
        for policy in component.policies:
            for ref in policy.evidence_refs:
                if ref not in valid_refs:
                    raise ValueError(f"Dangling evidence_ref '{ref}' in policy '{policy.id}' in {filepath}")
            for cond in policy.conditions:
                for ref in cond.evidence_refs:
                    if ref not in valid_refs:
                        raise ValueError(f"Dangling evidence_ref '{ref}' in condition '{cond.condition}' in {filepath}")
                        
        for priority in component.priorities:
            for ref in priority.evidence_refs:
                if ref not in valid_refs:
                    raise ValueError(f"Dangling evidence_ref '{ref}' in priority '{priority.id}' in {filepath}")
                    
        for dg in component.disputed_guidance:
            for pos in dg.positions:
                for ref in pos.evidence_refs:
                    if ref not in valid_refs:
                        raise ValueError(f"Dangling evidence_ref '{ref}' in disputed_guidance '{dg.id}' in {filepath}")

    def get_component(self, category: str, component_id: str) -> Optional[KnowledgeComponent]:
        if category not in self._components:
            raise ValueError(f"Unknown category: {category}")
        return self._components[category].get(component_id)
        
    def get_all_components(self, category: str) -> Dict[str, KnowledgeComponent]:
        if category not in self._components:
            raise ValueError(f"Unknown category: {category}")
        return self._components[category]
