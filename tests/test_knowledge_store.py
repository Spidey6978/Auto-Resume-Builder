import pytest
from pathlib import Path
from src.core.knowledge.store import KnowledgeStore
from src.core.knowledge.models import PolicyStrength

def test_knowledge_store_loads_components():
    # Provide the path to the real data/knowledge directory 
    # (in a real scenario we'd use a fixture with temp dir, but this works for a quick sanity check)
    base_dir = Path(__file__).parent.parent / "data" / "knowledge"
    
    store = KnowledgeStore(str(base_dir))
    
    # Test global load
    doc_conventions = store.get_component("global", "document_conventions")
    assert doc_conventions is not None
    assert doc_conventions.type == "global"
    assert doc_conventions.policies[0].id == "page_policy"
    assert doc_conventions.policies[0].strength == PolicyStrength.STRONG_RECOMMENDATION
    assert doc_conventions.policies[0].recommendation["pages"] == 1
    
    # Test domain load
    consulting = store.get_component("domain", "management_consulting")
    assert consulting is not None
    assert consulting.type == "domain"
    assert any(p.id == "business_impact" for p in consulting.priorities)
    assert consulting.disputed_guidance[0].id == "gpa_inclusion"
    
    # Test document type load
    academic = store.get_component("document_type", "academic_cv")
    assert academic is not None
    assert academic.type == "document_type"
    assert academic.policies[0].id == "page_policy"
    assert academic.policies[0].recommendation["pages"] == "unrestricted"
    
    # Test that getting an unknown category raises ValueError
    with pytest.raises(ValueError):
        store.get_component("unknown_category", "some_id")
        
    # Test that getting an unknown component returns None
    assert store.get_component("domain", "non_existent_domain") is None
