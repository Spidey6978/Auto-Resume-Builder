import pytest
import yaml
from pathlib import Path
from core.knowledge.models import (
    KnowledgeComponent, KnowledgeComponentType, PolicyStrength
)
from core.knowledge.store import KnowledgeStore

@pytest.fixture
def temp_knowledge_dir(tmp_path):
    # Setup temporary directory structure
    global_dir = tmp_path / "global"
    domain_dir = tmp_path / "domains"
    global_dir.mkdir()
    domain_dir.mkdir()
    
    # Write a test global component
    global_data = {
        "schema_version": "1.0",
        "id": "test_global",
        "type": "global",
        "policies": [
            {
                "id": "test_policy",
                "strength": "strong_recommendation",
                "recommendation": {"setting": True},
                "evidence_refs": ["ref_1"]
            }
        ],
        "priorities": [],
        "disputed_guidance": [],
        "sources": {
            "ref_1": {"title": "Test Source", "source_type": "test"}
        }
    }
    with open(global_dir / "test_global.yaml", "w") as f:
        yaml.dump(global_data, f)
        
    # Write a test domain component
    domain_data = {
        "schema_version": "1.0",
        "id": "test_domain",
        "type": "domain",
        "priorities": [
            {
                "id": "test_priority",
                "importance": "high",
                "evidence_refs": ["ref_2"]
            }
        ],
        "policies": [],
        "disputed_guidance": [],
        "sources": {
            "ref_2": {"title": "Test Domain Source", "source_type": "test"}
        }
    }
    with open(domain_dir / "test_domain.yaml", "w") as f:
        yaml.dump(domain_data, f)
        
    return tmp_path

def test_knowledge_store_loads_components(temp_knowledge_dir):
    store = KnowledgeStore(str(temp_knowledge_dir))
    
    # Test global load
    doc_conventions = store.get_component("global", "test_global")
    assert doc_conventions is not None
    assert doc_conventions.type == "global"
    assert doc_conventions.policies[0].id == "test_policy"
    assert doc_conventions.policies[0].strength == PolicyStrength.STRONG_RECOMMENDATION
    assert doc_conventions.policies[0].recommendation["setting"] is True
    
    # Test domain load
    domain = store.get_component("domain", "test_domain")
    assert domain is not None
    assert domain.type == "domain"
    assert any(p.id == "test_priority" for p in domain.priorities)
    
    # Test unknown category/component
    with pytest.raises(ValueError):
        store.get_component("unknown_category", "some_id")
        
    assert store.get_component("domain", "non_existent_domain") is None

def test_evidence_refs_validation(tmp_path):
    domain_dir = tmp_path / "domains"
    domain_dir.mkdir()
    
    # Create invalid data with dangling reference
    invalid_data = {
        "schema_version": "1.0",
        "id": "invalid_domain",
        "type": "domain",
        "priorities": [
            {
                "id": "test_priority",
                "importance": "high",
                "evidence_refs": ["dangling_ref"]
            }
        ],
        "policies": [],
        "disputed_guidance": [],
        "sources": {} # Dangling ref not here
    }
    with open(domain_dir / "invalid_domain.yaml", "w") as f:
        yaml.dump(invalid_data, f)
        
    with pytest.raises(ValueError, match="Dangling evidence_ref"):
        KnowledgeStore(str(tmp_path))
