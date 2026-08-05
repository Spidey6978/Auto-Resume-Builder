import os
import tempfile
import gc
import pytest
from unittest.mock import patch, MagicMock
from arb.core.ai_gateway import AIGateway, classify_exception
from arb.core.cache import CacheManager


@pytest.fixture
def temp_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_ai_cache.db")
        cm = CacheManager(db_path=db_path)
        yield cm
        gc.collect()


def test_exception_classifier():
    assert classify_exception(Exception("HTTP 429 ResourceExhausted: Rate limit exceeded"))[0] == "transient"
    assert classify_exception(Exception("HTTP 503 Service Unavailable"))[0] == "transient"
    assert classify_exception(Exception("HTTP 401 Unauthorized"))[0] == "fatal"
    assert classify_exception(Exception("HTTP 400 Invalid argument"))[0] == "fatal"


def test_generate_text_mock_ai():
    gateway = AIGateway(api_key="mock")
    result = gateway.generate_text("Prompt", mock_ai=True, model_hint="TestHint")
    assert "Mocked AI response for TestHint" in result
