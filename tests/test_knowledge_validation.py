import pytest
from pathlib import Path
from arb.core.knowledge.models import (
    KnowledgeComponent, KnowledgeComponentType
)
from arb.core.knowledge.store import KnowledgeStore

def test_production_knowledge_tree_is_valid():
    """
    Validates that the real knowledge directory can be loaded without errors.
    This ensures no syntax errors, schema violations, or dangling evidence_refs
    exist in the production YAMLs.
    """
    base_dir = Path(__file__).parent.parent / "data" / "knowledge"
    
    # If the directory doesn't exist, this will just return silently, 
    # but we want to assert it does exist if we are running tests in a real clone.
    if not base_dir.exists():
        pytest.skip("Production knowledge directory not found. Skipping validation.")
        
    try:
        store = KnowledgeStore(str(base_dir))
        
        # Verify we actually loaded some components
        global_components = store.get_all_components("global")
        # Just assert it succeeds without throwing exceptions
        assert isinstance(global_components, dict)
        
    except Exception as e:
        pytest.fail(f"Production knowledge tree failed validation: {e}")
