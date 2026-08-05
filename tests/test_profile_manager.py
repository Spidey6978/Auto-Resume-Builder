import os
import tempfile
import pytest

from arb.core.normalizer import normalize_languages
from arb.core.profile_manager import ProfileManager
from arb.core.fact_extractor import ExtractionResult, ExtractionStatus
from arb.models.domain import Fact, Project, CanonicalProfile


def test_normalize_languages_proportional():
    languages = {
        "Python": 45000,
        "Solidity": 12000,
        "HTML": 500,
        "Makefile": 200
    }
    normalized = normalize_languages(languages)
    # Total = 57700. 3% is 1731. HTML and Makefile should be dropped.
    assert normalized == ["Python", "Solidity"]
    
def test_normalize_languages_frontend_heavy():
    languages = {
        "HTML": 40000,
        "CSS": 35000,
        "JavaScript": 20000
    }
    normalized = normalize_languages(languages)
    assert normalized == ["HTML", "CSS", "JavaScript"]

def test_normalize_languages_empty():
    assert normalize_languages({}) == []


@pytest.fixture
def temp_yaml():
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_scenario_1_new_github_project(temp_yaml):
    manager = ProfileManager(temp_yaml)
    
    extracted = ExtractionResult(
        facts=[Fact(id="f1", text="new fact", fact_type="general", source_refs=["github:user/repo"])],
        status=ExtractionStatus.SUCCESS
    )
    
    manager.upsert_project(
        source_id="github:user/repo",
        raw_name="Awesome Repo",
        link="https://link",
        normalized_languages=["Python", "C++"],
        extraction_result=extracted
    )
    
    assert len(manager.profile.projects) == 1
    proj = manager.profile.projects[0]
    assert proj.id == "github:user/repo"
    assert proj.name == "Awesome Repo"
    assert proj.tech_stack == ["Python", "C++"]
    assert len(proj.facts) == 1


def test_scenario_2_existing_project_refresh_preserves_human_fields(temp_yaml):
    # Setup initial state with human edits
    manager = ProfileManager(temp_yaml)
    manager.profile.projects.append(Project(
        id="github:user/repo",
        name="Human Edited Name",
        link="https://custom-link",
        category=["backend", "distributed"],
        tech_stack=["React", "Python"],
        facts=[
            Fact(id="manual1", text="Manual fact", fact_type="general", source_refs=["manual"]),
            Fact(id="old_git1", text="Old github fact", fact_type="general", source_refs=["github:user/repo"])
        ]
    ))
    
    # New extraction from github
    extracted = ExtractionResult(
        facts=[Fact(id="new_git1", text="New github fact", fact_type="general", source_refs=["github:user/repo"])],
        status=ExtractionStatus.SUCCESS
    )
    
    manager.upsert_project(
        source_id="github:user/repo",
        raw_name="Original Repo Name",
        link="https://original-link",
        normalized_languages=["Python", "Solidity"],
        extraction_result=extracted
    )
    
    proj = manager.profile.projects[0]
    # 1. Human fields survived
    assert proj.name == "Human Edited Name"
    assert proj.link == "https://custom-link"
    assert proj.category == ["backend", "distributed"]
    
    # 2. Tech stack order preserved & unioned
    assert proj.tech_stack == ["React", "Python", "Solidity"]
    
    # 3. Provenance replacement successful
    assert len(proj.facts) == 2
    assert proj.facts[0].id == "manual1"  # survived!
    assert proj.facts[1].id == "new_git1" # appended!
    # old_git1 is gone.


def test_scenario_3_extraction_failure_is_non_destructive(temp_yaml):
    manager = ProfileManager(temp_yaml)
    manager.profile.projects.append(Project(
        id="github:user/repo",
        name="Repo",
        facts=[
            Fact(id="git1", text="Good fact", fact_type="general", source_refs=["github:user/repo"])
        ]
    ))
    
    failed_extraction = ExtractionResult(
        facts=[],
        status=ExtractionStatus.AI_ERROR
    )
    
    manager.upsert_project(
        source_id="github:user/repo",
        raw_name="Repo",
        link=None,
        normalized_languages=[],
        extraction_result=failed_extraction
    )
    
    # Existing fact MUST be preserved since extraction failed
    proj = manager.profile.projects[0]
    assert len(proj.facts) == 1
    assert proj.facts[0].id == "git1"


def test_scenario_4_idempotency_of_identical_ingestion(temp_yaml):
    manager = ProfileManager(temp_yaml)
    
    extracted = ExtractionResult(
        facts=[Fact(id="f1", text="identical fact", fact_type="general", source_refs=["github:user/repo"])],
        status=ExtractionStatus.SUCCESS
    )
    
    # Run sync 3 times
    for _ in range(3):
        manager.upsert_project(
            source_id="github:user/repo",
            raw_name="Repo",
            link=None,
            normalized_languages=["Python"],
            extraction_result=extracted
        )
        
    proj = manager.profile.projects[0]
    # No duplicates, no re-ordering
    assert len(manager.profile.projects) == 1
    assert proj.tech_stack == ["Python"]
    assert len(proj.facts) == 1
    assert proj.facts[0].id == "f1"
    
def test_atomic_persistence(temp_yaml):
    manager = ProfileManager(temp_yaml)
    manager.profile.schema_version = 42
    
    manager.save()
    
    assert os.path.exists(temp_yaml)
    loaded = ProfileManager(temp_yaml)
    assert loaded.profile.schema_version == 42


def test_malformed_yaml_fails_fast(temp_yaml):
    # Write garbage to the YAML file
    with open(temp_yaml, "w") as f:
        f.write("this is [} malformed yaml \n - : : what")
        
    with pytest.raises(RuntimeError, match="CRITICAL: Failed to parse existing canonical profile"):
        ProfileManager(temp_yaml)
