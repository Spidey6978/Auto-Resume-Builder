import os
import tempfile
import pytest
from models.domain import (
    Fact,
    Project,
    ExperienceItem,
    AwardItem,
    EducationItem,
    PersonalInfo,
    SourceStatus,
    SourceResult,
    CanonicalProfile,
    SourceRef,
    EvidenceItem
)


def test_fact_instantiation_and_dict_conversion():
    fact = Fact(
        id="raytracer-kerr",
        text="Implemented near-extremal Kerr null geodesics",
        fact_type="implementation",
        metric="60 FPS",
        tags=["physics", "numerical-methods"],
        source_refs=[SourceRef(type="github", id="null-geodesic-raytracer")]
    )
    d = fact.to_dict()
    assert d["id"] == "raytracer-kerr"
    assert d["metric"] == "60 FPS"
    assert d["tags"] == ["physics", "numerical-methods"]
    assert d["source_refs"] == [{"type": "github", "id": "null-geodesic-raytracer"}]

    restored = Fact.from_dict(d)
    assert restored == fact


def test_project_multi_category_and_facts():
    fact = Fact(
        id="transit-offline",
        text="Built offline-first ticket validation engine",
        fact_type="architecture",
        metric="50+ tx/sec",
        tags=["solidity", "fastapi"]
    )
    proj = Project(
        id="transitos",
        name="TransitOS",
        link="https://github.com/Spidey6978/TransitOS",
        tech_stack=["Python", "Solidity", "FastAPI"],
        category=["blockchain", "backend", "distributed-systems"],
        facts=[fact]
    )
    d = proj.to_dict()
    assert d["category"] == ["blockchain", "backend", "distributed-systems"]
    assert len(d["facts"]) == 1

    restored = Project.from_dict(d)
    assert restored.id == "transitos"
    assert len(restored.facts) == 1
    assert restored.facts[0].id == "transit-offline"


def test_experience_and_award_items():
    fact = Fact(id="wie-web", text="Maintained chapter web infrastructure", fact_type="leadership")
    exp = ExperienceItem(
        id="ieee-wie",
        organization="IEEExWIE SFIT",
        title="Webmaster",
        location="Mumbai, India",
        start_date="2026-Current",
        facts=[fact]
    )
    assert exp.organization == "IEEExWIE SFIT"
    assert exp.facts[0].id == "wie-web"

    award = AwardItem(
        id="codesangram-1st",
        title="1st Place, Blockchain Track",
        event="CodeSangram Hackathon",
        year=2026,
        facts=[Fact(id="cs-win", text="Won 1st place with TransitOS", fact_type="achievement")]
    )
    assert award.year == 2026
    assert len(award.facts) == 1


def test_source_result_ingestion_boundary():
    result = SourceResult(
        source_type="github",
        source_id="Spidey6978/TransitOS",
        evidence=[EvidenceItem(id="e1", kind="readme", content="README raw content string")],
        metadata={"stars": 42},
        status=SourceStatus.SUCCESS
    )
    d = result.to_dict()
    assert d["status"] == "success"
    assert d["metadata"]["stars"] == 42
    assert d["evidence"][0]["kind"] == "readme"


def test_canonical_profile_yaml_roundtrip():
    profile = CanonicalProfile(
        schema_version=1,
        personal=PersonalInfo(
            name="Veer Gopani",
            email="veergopani70@gmail.com",
            github="https://github.com/Spidey6978",
            linkedin="https://linkedin.com/in/veer-gopani",
            location="Mumbai, India"
        ),
        education=[
            EducationItem(
                id="sfit",
                institution="St. Francis Institute of Technology (SFIT)",
                degree="B.E.",
                field="Information Technology",
                location="Mumbai, India",
                start_date="2024",
                end_date="2028"
            )
        ],
        projects=[
            Project(
                id="raytracer",
                name="Null Geodesic Raytracer",
                tech_stack=["Python", "Numba"],
                category=["computational-physics", "hpc"],
                facts=[
                    Fact(
                        id="rk4-integration",
                        text="Built black-hole ray tracer using RK4 null-geodesic integration",
                        fact_type="math_physics",
                        metric="60 FPS"
                    )
                ]
            )
        ],
        skills={"Languages": ["Python", "C++", "Java"]}
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = os.path.join(tmpdir, "canonical_profile.yaml")
        profile.to_yaml(yaml_path)

        assert os.path.exists(yaml_path)

        loaded = CanonicalProfile.from_yaml(yaml_path)
        assert loaded.schema_version == 1
        assert loaded.personal.name == "Veer Gopani"
        assert len(loaded.projects) == 1
        assert loaded.projects[0].category == ["computational-physics", "hpc"]
        assert loaded.projects[0].facts[0].metric == "60 FPS"
        assert loaded.skills["Languages"] == ["Python", "C++", "Java"]
