import os
import yaml
from typing import Dict, Optional
from pathlib import Path
from src.core.knowledge.models import KnowledgeComponent

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
        if component.type != category:
            raise ValueError(f"Component type '{component.type}' does not match directory category '{category}' in {filepath}")
            
        self._components[category][component.id] = component

    def get_component(self, category: str, component_id: str) -> Optional[KnowledgeComponent]:
        if category not in self._components:
            raise ValueError(f"Unknown category: {category}")
        return self._components[category].get(component_id)
        
    def get_all_components(self, category: str) -> Dict[str, KnowledgeComponent]:
        if category not in self._components:
            raise ValueError(f"Unknown category: {category}")
        return self._components[category]
