import json
import pytest
from unittest.mock import MagicMock
from arb.models.domain import SourceResult, SourceStatus, Fact, EvidenceItem
from arb.core.ai_gateway import AIGateway
from arb.core.fact_extractor import FactExtractor, ExtractionStatus


@pytest.fixture
def mock_gateway():
    gateway = MagicMock(spec=AIGateway)
    return gateway


@pytest.fixture
def extractor(mock_gateway):
    return FactExtractor(ai_gateway=mock_gateway, cache_manager=MagicMock())


def test_clean_json_response_with_fences(extractor):
    raw_response = "```json\n[\n  {\"text\": \"fact 1\"}\n]\n```"
    cleaned = extractor._clean_json_response(raw_response)
    assert cleaned == "[\n  {\"text\": \"fact 1\"}\n]"


def test_clean_json_response_without_fences(extractor):
    raw_response = "[\n  {\"text\": \"fact 1\"}\n]"
    cleaned = extractor._clean_json_response(raw_response)
    assert cleaned == "[\n  {\"text\": \"fact 1\"}\n]"


def test_deterministic_id_generation(extractor):
    text = "Uses encrypted local storage for offline ticket validation."
    fact_id = extractor._generate_fact_id("github:Spidey6978/TransitOS", "architecture", text)
    # Check stable deterministic hash prefix
    assert fact_id.startswith("transitos-architecture-")
    assert len(fact_id) > len("transitos-architecture-") + 5


def test_insufficient_source_handled_cleanly(extractor):
    source = SourceResult(
        source_id="empty-repo",
        source_type="github",
        evidence=[],  # insufficient source
        status=SourceStatus.SUCCESS
    )
    result = extractor.extract(source, "empty-repo")
    assert result.status == ExtractionStatus.INSUFFICIENT_SOURCE
    assert result.facts == []
    assert result.error is None


def test_invalid_json_response_handled_cleanly(extractor, mock_gateway):
    source = SourceResult(
        source_id="transitos",
        source_type="github",
        evidence=[EvidenceItem(id="e1", kind="readme", content="long enough readme string")],
        status=SourceStatus.SUCCESS
    )
    # Mock AI returning non-JSON garbage
    mock_gateway.generate_text.return_value = "Sorry, I can't do that."
    
    result = extractor.extract(source, "transitos")
    assert result.status == ExtractionStatus.INVALID_RESPONSE
    assert result.facts == []


def test_successful_fact_extraction(extractor, mock_gateway):
    source = SourceResult(
        source_id="transitos",
        source_type="github",
        evidence=[EvidenceItem(id="e1", kind="readme", content="long enough readme string")],
        status=SourceStatus.SUCCESS
    )
    
    # Mock AI returning proper JSON array
    mock_gateway.generate_text.return_value = """
    ```json
    [
      {
        "text": "Batched synchronization processes 50+ queued transactions per second.",
        "fact_type": "performance",
        "metric": "50+ tx/sec",
        "tags": ["polygon"],
        "provenance": {"type": "github", "id": "transitos"}
      },
      {
        "text": "Another basic fact.",
        "fact_type": "general",
        "provenance": {"type": "github", "id": "transitos"}
      }
    ]
    ```
    """
    
    result = extractor.extract(source, "transitos")
    
    assert result.status == ExtractionStatus.SUCCESS
    assert len(result.facts) == 2
    
    f1 = result.facts[0]
    assert f1.fact_type == "performance"
    assert f1.metric == "50+ tx/sec"
    assert "polygon" in f1.tags
    assert f1.source_refs[0].type == "github"
    assert f1.source_refs[0].id == "transitos"
    
    f2 = result.facts[1]
    assert f2.metric is None
    assert f2.source_refs[0].type == "github"
    assert f2.source_refs[0].id == "transitos"

