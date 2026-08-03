from unittest.mock import MagicMock
from core.generator import ContentGenerator, GenerationStatus
from models.domain import CanonicalProfile, Project, Fact, TargetContext
from models.plan import PlannedProject, PlannedFact

def test_generator_insufficient_data():
    generator = ContentGenerator(ai_gateway=MagicMock(), cache_manager=MagicMock())
    project = Project(id="1", name="No Facts", facts=[])
    profile = CanonicalProfile(projects=[project])
    planned_project = PlannedProject(project_id="1", selected_facts=[])
    
    target = TargetContext(id="test", description="desc")
    result = generator.generate_project_bullets(profile, planned_project, target=target)
    
    assert result.status == GenerationStatus.INSUFFICIENT_DATA
    assert result.bullets == []

def test_generator_success():
    mock_ai = MagicMock()
    # Mocking Gemini returning exactly 2 bullets
    mock_ai.generate_text.return_value = "- Architected a backend system.\n- Optimized database queries."
    
    mock_cache = MagicMock()
    mock_cache.get.return_value = None  # Cache miss
    
    generator = ContentGenerator(ai_gateway=mock_ai, cache_manager=mock_cache)
    project = Project(
        id="1", 
        name="Backend Repo", 
        facts=[Fact(id="f1", text="backend", fact_type="general", source_refs=["github"])]
    )
    profile = CanonicalProfile(projects=[project])
    planned_project = PlannedProject(project_id="1", selected_facts=[PlannedFact(fact_id="f1")])
    target = TargetContext(id="test", description="desc")
    result = generator.generate_project_bullets(profile, planned_project, target=target)
    
    assert result.status == GenerationStatus.SUCCESS
    assert len(result.bullets) == 2
    assert result.bullets[0] == "Architected a backend system."
    assert result.bullets[1] == "Optimized database queries."
    
    # Verify cache was set
    mock_cache.set.assert_called_once()

def test_generator_cache_hit():
    mock_ai = MagicMock()
    mock_cache = MagicMock()
    mock_cache.get.return_value = ["Cached bullet 1", "Cached bullet 2"]
    
    generator = ContentGenerator(ai_gateway=mock_ai, cache_manager=mock_cache)
    project = Project(id="1", name="Repo", facts=[Fact(id="f1", text="f", fact_type="general", source_refs=["github"])])
    profile = CanonicalProfile(projects=[project])
    planned_project = PlannedProject(project_id="1", selected_facts=[PlannedFact(fact_id="f1")])
    target = TargetContext(id="test", description="desc")
    result = generator.generate_project_bullets(profile, planned_project, target=target)
    
    assert result.status == GenerationStatus.SUCCESS
    assert result.bullets == ["Cached bullet 1", "Cached bullet 2"]
    mock_ai.generate_text.assert_not_called()  # Should not hit API
