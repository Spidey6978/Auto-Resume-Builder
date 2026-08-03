from unittest.mock import MagicMock
from core.target_engine import TargetEngine
from models.domain import CanonicalProfile, Project, Fact, TargetContext, TargetRule

def test_target_engine_filter_exclude():
    engine = TargetEngine(ai_gateway=MagicMock(), cache_manager=MagicMock())
    
    profile = CanonicalProfile(
        projects=[
            Project(id="p1", name="Project 1", facts=[]),
            Project(id="p2", name="Project 2", facts=[]),
            Project(id="p3", name="Project 3", facts=[])
        ]
    )
    
    target = TargetContext(
        id="test",
        description="desc",
        project_rules=TargetRule(exclude=["p2"])
    )
    
    # We mock _score_project_facts to just return the facts to isolate filtering
    engine._score_project_facts = MagicMock(side_effect=lambda p, t, mock_ai=False: (p.facts, "success"))
    
    plan = engine.create_plan(profile, target)
    
    assert len(plan.projects) == 2
    assert plan.projects[0].project_id == "p1"
    assert plan.projects[1].project_id == "p3"

def test_target_engine_filter_include_only():
    engine = TargetEngine(ai_gateway=MagicMock(), cache_manager=MagicMock())
    
    profile = CanonicalProfile(
        projects=[
            Project(id="p1", name="Project 1", facts=[]),
            Project(id="p2", name="Project 2", facts=[]),
            Project(id="p3", name="Project 3", facts=[])
        ]
    )
    
    target = TargetContext(
        id="test",
        description="desc",
        project_rules=TargetRule(include_only=["p2"])
    )
    
    engine._score_project_facts = MagicMock(side_effect=lambda p, t, mock_ai=False: (p.facts, "success"))
    plan = engine.create_plan(profile, target)
    
    assert len(plan.projects) == 1
    assert plan.projects[0].project_id == "p2"

def test_target_engine_scoring_mock_ai():
    mock_ai = MagicMock()
    # It shouldn't be called if mock_ai=True, but just in case
    engine = TargetEngine(ai_gateway=mock_ai, cache_manager=MagicMock())
    
    project = Project(
        id="p1", 
        name="Project 1", 
        facts=[
            Fact(id="f1", text="text1", fact_type="general"),
            Fact(id="f2", text="text2", fact_type="general"),
            Fact(id="f3", text="text3", fact_type="general"),
            Fact(id="f4", text="text4", fact_type="general"),
            Fact(id="f5", text="text5", fact_type="general"),
            Fact(id="f6", text="text6", fact_type="general")
        ]
    )
    
    target = TargetContext(id="test", description="desc")
    
    # Request max 3 facts
    best_facts, status = engine._score_project_facts(project, target, mock_ai=True, max_facts=3)
    
    assert len(best_facts) == 3
    assert best_facts[0].id == "f1"
    assert best_facts[1].id == "f2"
    assert best_facts[2].id == "f3"
