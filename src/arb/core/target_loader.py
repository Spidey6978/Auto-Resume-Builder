import os
import yaml
from typing import Optional
from arb.models.domain import TargetContext, TargetRule
from arb.core.target_resolver import TargetResolver

class TargetLoader:
    def __init__(self, targets_dir: str, target_resolver: TargetResolver):
        self.targets_dir = targets_dir
        self.resolver = target_resolver
        
    def _parse_rule(self, data: dict) -> TargetRule:
        if not data:
            return TargetRule()
        return TargetRule(
            exclude=data.get("exclude", []),
            include_only=data.get("include_only", [])
        )


    def load_target(self, target_name: Optional[str] = None, job_path: Optional[str] = None, mock_ai: bool = False) -> TargetContext:
        """Loads a TargetContext either from a job description file or a target YAML."""
        if job_path:
            if not os.path.exists(job_path):
                raise FileNotFoundError(f"Job description file not found: {job_path}")
            with open(job_path, "r", encoding="utf-8") as f:
                desc = f.read().strip()
            return self.resolver.resolve(target_id=os.path.basename(job_path), raw_description=desc, mock_ai=mock_ai)
            
        if target_name:
            if os.path.exists(target_name):
                yaml_path = target_name
            else:
                candidate = os.path.join(self.targets_dir, f"{target_name}.yaml")
                if os.path.exists(candidate):
                    yaml_path = candidate
                else:
                    from arb.core.paths import get_user_data_dir
                    user_target = os.path.join(get_user_data_dir(), "targets", f"{target_name}.yaml")
                    if os.path.exists(user_target):
                        yaml_path = user_target
                    else:
                        raise FileNotFoundError(f"Target loadout not found: {target_name} (checked {candidate})")
                
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

                
            rules_data = data.get("rules", {})
            return self.resolver.resolve(
                target_id=target_name,
                raw_description=data.get("description", "A general software engineering role."),
                domain_id=data.get("domain", None),
                project_rules=self._parse_rule(rules_data.get("projects", {})),
                experience_rules=self._parse_rule(rules_data.get("experience", {})),
                mock_ai=mock_ai
            )
            
        # Default fallback
        return self.resolver.resolve(target_id="general", raw_description="A general software engineering role.", domain_id="engineering", mock_ai=mock_ai)
