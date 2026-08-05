import os
from typing import Dict, Optional
import logging
from arb.models.config import DomainConfig

logger = logging.getLogger(__name__)

class DomainLoader:
    def __init__(self, domains_dir: str):
        self.domains_dir = domains_dir
        self.domains: Dict[str, DomainConfig] = {}
        self._load_all()

    def _load_all(self):
        if not os.path.exists(self.domains_dir):
            logger.warning(f"Domains directory not found: {self.domains_dir}")
            return
            
        for filename in os.listdir(self.domains_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                filepath = os.path.join(self.domains_dir, filename)
                try:
                    config = DomainConfig.from_yaml(filepath)
                    self.domains[config.id] = config
                    logger.debug(f"Loaded domain config: {config.id}")
                except Exception as e:
                    raise RuntimeError(f"Invalid domain configuration '{filename}': {e}") from e

    def get_domain(self, domain_id: str) -> Optional[DomainConfig]:
        return self.domains.get(domain_id)

    def list_domains(self) -> Dict[str, DomainConfig]:
        return self.domains
