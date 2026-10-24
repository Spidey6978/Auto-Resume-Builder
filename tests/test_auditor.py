import pytest
from arb.models.domain import CanonicalProfile, Project, Fact, SourceRef
from arb.models.presentation import ResumeDocument, RenderedProject, RenderedBullet
from arb.core.auditor import EvidenceAuditor, AuditReport


def test_auditor_all_grounded():
    fact1 = Fact(id="f1", text="Built auth in Go", fact_type="general", metric="99.9%", source_refs=[SourceRef(type="github", id="repo1")])
    project = Project(id="p1", name="Auth Service", facts=[fact1])
    profile = CanonicalProfile(projects=[project])

    bullet = RenderedBullet(text="Built auth in Go with 99.9% uptime", source_fact_ids=["f1"], relevance_score=0.95)
    rendered_project = RenderedProject(id="p1", name="Auth Service", link=None, tech_stack=["Go"], bullets=[bullet])
    document = ResumeDocument(
        personal=None,
        education=[],
        experience=[],
        awards=[],
        projects=[rendered_project],
        skills={}
    )

    auditor = EvidenceAuditor()
    report = auditor.audit(document, profile, model_name="Gemma 4")

    assert report.total_bullets == 1
    assert report.grounded_bullets == 1
    assert report.ungrounded_bullets == 0
    assert report.groundedness_score == 100.0
    assert report.items[0].is_grounded is True
    assert report.items[0].supporting_facts[0]["id"] == "f1"
    assert report.items[0].supporting_facts[0]["metric"] == "99.9%"

    md = report.to_markdown()
    assert "PASSED" in md
    assert "Gemma 4" in md
    assert "Auth Service" in md


def test_auditor_detects_hallucinated_bullet_without_citation():
    project = Project(id="p1", name="Project A", facts=[])
    profile = CanonicalProfile(projects=[project])

    bullet = RenderedBullet(text="Invented quantum time travel", source_fact_ids=[])
    rendered_project = RenderedProject(id="p1", name="Project A", link=None, tech_stack=[], bullets=[bullet])
    document = ResumeDocument(
        personal=None,
        education=[],
        experience=[],
        awards=[],
        projects=[rendered_project],
        skills={}
    )

    auditor = EvidenceAuditor()
    report = auditor.audit(document, profile)

    assert report.total_bullets == 1
    assert report.grounded_bullets == 0
    assert report.ungrounded_bullets == 1
    assert report.groundedness_score == 0.0
    assert report.items[0].is_grounded is False
    assert "Hallucination risk" in report.items[0].warning

    md = report.to_markdown()
    assert "UNGROUNDED CLAIM" in md


def test_auditor_detects_nonexistent_fact_id():
    fact1 = Fact(id="valid_fact", text="Valid claim", fact_type="general", source_refs=[])
    project = Project(id="p1", name="Project A", facts=[fact1])
    profile = CanonicalProfile(projects=[project])

    bullet = RenderedBullet(text="Claim referencing ghost fact", source_fact_ids=["nonexistent_id"])
    rendered_project = RenderedProject(id="p1", name="Project A", link=None, tech_stack=[], bullets=[bullet])
    document = ResumeDocument(
        personal=None,
        education=[],
        experience=[],
        awards=[],
        projects=[rendered_project],
        skills={}
    )

    auditor = EvidenceAuditor()
    report = auditor.audit(document, profile)

    assert report.items[0].is_grounded is False
    assert "Invalid fact citation" in report.items[0].warning
