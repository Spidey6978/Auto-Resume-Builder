from unittest.mock import MagicMock
from core.knowledge.evaluator import CandidateState, PolicyEvaluator
from models.domain import CanonicalProfile, TargetContext, ExperienceItem, AwardItem, Project
from core.knowledge.models import (
    KnowledgeComponent, ConditionalPolicy, RecommendationCondition, Priority
)

def test_candidate_state():
    profile = CanonicalProfile(
        experience=[
            ExperienceItem(id="e1", organization="Org", title="Dev"),
            ExperienceItem(id="e2", organization="Org", title="Dev"),
            ExperienceItem(id="e3", organization="Org", title="Dev")
        ],
        awards=[
            AwardItem(id="a1", title="Published paper in IEEE")
        ]
    )
    target = TargetContext(id="t1", description="desc")
    
    state = CandidateState(profile, target)
    
    assert state.substantial_relevant_history is True
    assert state.has_publications is True
    
    # Empty profile
    state_empty = CandidateState(CanonicalProfile(), target)
    assert state_empty.substantial_relevant_history is False
    assert state_empty.has_publications is False

def test_policy_evaluator_hierarchy():
    mock_store = MagicMock()
    
    global_comp = KnowledgeComponent(
        id="global",
        type="global",
        policies=[
            ConditionalPolicy(id="page_policy", recommendation={"pages": 1})
        ]
    )
    
    doc_comp = KnowledgeComponent(
        id="industry_resume",
        type="document_type",
        policies=[
            ConditionalPolicy(id="page_policy", recommendation={"pages": 2}) # Should override global
        ],
        priorities=[
            Priority(id="p1", importance="high")
        ]
    )
    
    domain_comp = KnowledgeComponent(
        id="software_engineering",
        type="domain",
        policies=[
            ConditionalPolicy(id="section_order", recommendation={"order": ["projects", "experience"]})
        ]
    )
    
    def mock_get_component(category, comp_id):
        if category == "document_type" and comp_id == "industry_resume": return doc_comp
        if category == "domain" and comp_id == "software_engineering": return domain_comp
        raise ValueError()
        
    def mock_get_all_components(category):
        if category == "global": return {"global": global_comp}
        raise ValueError()
        
    mock_store.get_component.side_effect = mock_get_component
    mock_store.get_all_components.side_effect = mock_get_all_components
    
    evaluator = PolicyEvaluator(store=mock_store)
    
    profile = CanonicalProfile()
    target = TargetContext(id="t1", description="desc", document_type="industry_resume", domain_id="software_engineering")
    
    resolved = evaluator.evaluate(profile, target)
    
    # doc_type should override global for page_policy
    assert resolved.policies["page_policy"] == {"pages": 2}
    # section_order from domain
    assert resolved.policies["section_order"] == {"order": ["projects", "experience"]}
    # Priority collected
    assert len(resolved.active_priorities) == 1
    assert resolved.active_priorities[0]["id"] == "p1"
