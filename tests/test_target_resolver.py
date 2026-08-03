from unittest.mock import MagicMock
from src.core.target_resolver import JobDescriptionExtractor, TargetResolver
from src.models.domain import TargetContext, TargetRule

def test_job_description_extractor_success():
    mock_ai = MagicMock()
    # Mock LLM returning valid JSON
    mock_ai.generate_text.return_value = 'Here is the parsed output: {"domain": "software_engineering", "specialization": "backend", "career_stage": "entry_level", "hard_skills": ["python", "docker"], "implied_traits": ["fast-paced"]}'
    
    extractor = JobDescriptionExtractor(ai_gateway=mock_ai)
    
    result = extractor.extract(
        jd_text="Looking for a junior backend engineer who knows python and docker for our fast-paced startup.",
        valid_domains=["software_engineering"],
        valid_specializations=["backend", "frontend"],
        valid_career_stages=["entry_level", "senior"]
    )
    
    assert result.get("domain") == "software_engineering"
    assert result.get("specialization") == "backend"
    assert result.get("career_stage") == "entry_level"
    assert "python" in result.get("hard_skills", [])
    assert "fast-paced" in result.get("implied_traits", [])

def test_job_description_extractor_invalid_json():
    mock_ai = MagicMock()
    # Mock LLM returning garbage
    mock_ai.generate_text.return_value = 'I am sorry, I cannot do that.'
    
    extractor = JobDescriptionExtractor(ai_gateway=mock_ai)
    
    result = extractor.extract(
        jd_text="Looking for someone.",
        valid_domains=[],
        valid_specializations=[],
        valid_career_stages=[]
    )
    
    # Should safely fallback to empty dict
    assert result == {}

def test_target_resolver():
    # Setup mock extractor
    mock_extractor = MagicMock()
    mock_extractor.extract.return_value = {
        "domain": "management_consulting",
        "specialization": None,
        "career_stage": "senior",
        "hard_skills": ["excel"],
        "implied_traits": ["client-facing"]
    }
    
    # Setup mock knowledge store
    mock_store = MagicMock()
    mock_store.get_all_components.side_effect = lambda category: {
        "domain": {"management_consulting": MagicMock(), "software_engineering": MagicMock()},
        "specialization": {},
        "career_stage": {"senior": MagicMock(), "entry_level": MagicMock()}
    }.get(category, {})
    
    resolver = TargetResolver(extractor=mock_extractor, knowledge_store=mock_store)
    
    target_rule = TargetRule(exclude=["p1"])
    context = resolver.resolve(
        target_id="consulting_role",
        raw_description="Senior consultant needed.",
        project_rules=target_rule
    )
    
    assert context.id == "consulting_role"
    assert context.description == "Senior consultant needed."
    assert context.domain == "management_consulting"
    assert context.specialization is None
    assert context.career_stage == "senior"
    assert context.hard_skills == ["excel"]
    assert context.implied_traits == ["client-facing"]
    assert context.project_rules.exclude == ["p1"]
