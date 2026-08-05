from unittest.mock import MagicMock
from arb.core.target_engine import TargetEngine
from arb.models.domain import CanonicalProfile, Project, Fact, TargetContext, TargetRule

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
    
    # We mock FactRanker.rank_facts to just return the facts to isolate filtering
    mock_ranker = MagicMock()
    mock_ranker.rank_facts.side_effect = lambda p, t, pol, mock_ai=False: (p.facts, "success")
    engine.ranker = mock_ranker
    
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
    
    mock_ranker = MagicMock()
    mock_ranker.rank_facts.side_effect = lambda p, t, pol, mock_ai=False: (p.facts, "success")
    engine.ranker = mock_ranker
    
    plan = engine.create_plan(profile, target)
    
    assert len(plan.projects) == 1
    assert plan.projects[0].project_id == "p2"


