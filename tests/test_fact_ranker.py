from unittest.mock import MagicMock
from core.fact_ranker import FactRanker, ScoredFact
from models.domain import Fact, TargetContext, Project
from models.plan import ResolvedPolicies

def test_deterministic_scoring():
    ranker = FactRanker(ai_gateway=MagicMock(), cache_manager=MagicMock())
    
    # Priority demands "business_impact" and "leadership"
    policies = ResolvedPolicies(
        active_priorities=[
            {"id": "business_impact", "importance": "high"},
            {"id": "leadership", "importance": "critical"}
        ]
    )
    
    # Target requires Python and distributed systems
    target = TargetContext(
        id="t1",
        description="We need a python dev for distributed systems in a fast-paced environment",
        hard_skills=["python", "distributed systems"],
        implied_traits=["fast-paced"]
    )
    
    # Fact 1: Has metric, matches hard skill (Python), matches trait (fast-paced)
    f1 = Fact(
        id="f1",
        text="Built a python service in a fast-paced team that increased throughput by 20%.",
        fact_type="implementation",
        metric="20%"
    )
    
    # Fact 2: Matches priority (leadership, critical = 3.0), has provenance
    f2 = Fact(
        id="f2",
        text="Led a team of 5 engineers to deliver the project on time.",
        fact_type="leadership",
        source_refs=["src1", "src2"]
    )
    
    # Fact 3: Irrelevant fact
    f3 = Fact(
        id="f3",
        text="Wrote some HTML.",
        fact_type="implementation"
    )
    
    score1 = ranker._deterministic_score(f1, target, policies)
    # 2.0 (metric) + 3.0 (python) + 1.5 (fast-paced) = 6.5
    assert score1.score == 6.5
    assert "has_metric" in score1.reasons
    assert "matches_hard_skill:python" in score1.reasons
    
    score2 = ranker._deterministic_score(f2, target, policies)
    # 3.0 (leadership critical) + 0.4 (2 sources) = 3.4
    assert score2.score == 3.4
    assert "matches_priority:leadership" in score2.reasons
    assert "has_provenance" in score2.reasons
    
    score3 = ranker._deterministic_score(f3, target, policies)
    assert score3.score == 0.0

def test_needs_semantic_rerank():
    ranker = FactRanker(ai_gateway=MagicMock(), cache_manager=MagicMock())
    
    # Not enough facts to care
    assert ranker._needs_semantic_rerank([ScoredFact(Fact(id="f", text="", fact_type=""), 5.0, [])], 5) is False
    
    # Low scores (highest is < 2.0)
    low_scores = [ScoredFact(Fact(id=f"f{i}", text="", fact_type=""), 1.0, []) for i in range(6)]
    assert ranker._needs_semantic_rerank(low_scores, 5) is True
    
    # Tie at the boundary (max_facts = 3)
    tie_scores = [
        ScoredFact(Fact(id="f1", text="", fact_type=""), 10.0, []),
        ScoredFact(Fact(id="f2", text="", fact_type=""), 9.0, []),
        ScoredFact(Fact(id="f3", text="", fact_type=""), 5.5, []), # Cutoff
        ScoredFact(Fact(id="f4", text="", fact_type=""), 5.0, []), # Just below cutoff (diff = 0.5)
        ScoredFact(Fact(id="f5", text="", fact_type=""), 2.0, []),
    ]
    assert ranker._needs_semantic_rerank(tie_scores, 3) is True
    
    # No tie at boundary (max_facts = 3)
    clear_scores = [
        ScoredFact(Fact(id="f1", text="", fact_type=""), 10.0, []),
        ScoredFact(Fact(id="f2", text="", fact_type=""), 9.0, []),
        ScoredFact(Fact(id="f3", text="", fact_type=""), 8.0, []), # Cutoff
        ScoredFact(Fact(id="f4", text="", fact_type=""), 2.0, []), # Just below cutoff (diff = 6.0)
        ScoredFact(Fact(id="f5", text="", fact_type=""), 1.0, []),
    ]
    assert ranker._needs_semantic_rerank(clear_scores, 3) is False

def test_rank_facts_deterministic_confident():
    ranker = FactRanker(ai_gateway=MagicMock(), cache_manager=MagicMock())
    
    project = Project(
        id="p1", name="p1",
        facts=[
            Fact(id="f1", text="Wrote HTML", fact_type="implementation"),
            Fact(id="f2", text="Used Python", fact_type="implementation"),
            Fact(id="f3", text="Used AWS", fact_type="implementation"),
            Fact(id="f4", text="Used Docker", fact_type="implementation"),
            Fact(id="f5", text="Used K8s", fact_type="implementation"),
            Fact(id="f6", text="Irrelevant", fact_type="implementation")
        ]
    )
    
    target = TargetContext(
        id="t1", description="desc",
        hard_skills=["python", "aws", "docker", "k8s"] # Will give them 3.0 points each
    )
    policies = ResolvedPolicies()
    
    best_facts, status = ranker.rank_facts(project, target, policies, max_facts=4)
    
    assert status == "deterministic_confident"
    assert len(best_facts) == 4
    # f6 and f1 should be dropped
    ids = [f.fact.id for f in best_facts]
    assert "f6" not in ids
    assert "f1" not in ids
