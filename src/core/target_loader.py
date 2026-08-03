import os
import yaml
from typing import Optional
from models.domain import TargetContext, TargetRule

class TargetLoader:
    def __init__(self, targets_dir: str):
        self.targets_dir = targets_dir
        
    def _parse_rule(self, data: dict) -> TargetRule:
        if not data:
            return TargetRule()
        return TargetRule(
            exclude=data.get("exclude", []),
            include_only=data.get("include_only", [])
        )

    def load_target(self, target_name: Optional[str] = None, job_path: Optional[str] = None) -> TargetContext:
        """
        Loads a TargetContext either from a predefined loadout YAML or a raw JD text file.
        If neither is provided, returns a 'general' default target.
        """
        if job_path:
            if not os.path.exists(job_path):
                raise FileNotFoundError(f"Job description file not found: {job_path}")
            with open(job_path, "r", encoding="utf-8") as f:
                desc = f.read().strip()
            return TargetContext(id=os.path.basename(job_path), description=desc)
            
        if target_name:
            # Look for targets/{target_name}.yaml
            yaml_path = os.path.join(self.targets_dir, f"{target_name}.yaml")
            if not os.path.exists(yaml_path):
                raise FileNotFoundError(f"Target loadout not found: {yaml_path}")
                
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                
            rules_data = data.get("rules", {})
            return TargetContext(
                id=target_name,
                description=data.get("description", "A general software engineering role."),
                project_rules=self._parse_rule(rules_data.get("projects", {})),
                experience_rules=self._parse_rule(rules_data.get("experience", {}))
            )
            
        # Default fallback
        return TargetContext(id="general", description="A general software engineering role.")
