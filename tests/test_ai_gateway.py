import os
import tempfile
import gc
import pytest
from unittest.mock import patch, MagicMock
from arb.core.ai_config import AIConfig
from arb.core.ai_gateway import (
    AIGateway,
    OllamaProvider,
    GeminiProvider,
    MockProvider,
    classify_exception
)
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


def test_ollama_provider_offline():
    provider = OllamaProvider(base_url="http://127.0.0.1:99999", model="gemma4:e2b")
    assert provider.is_available() is False
    with pytest.raises(RuntimeError) as exc:
        provider.generate_text("test")
    assert "Ollama is not running" in str(exc.value)


def test_ollama_provider_success():
    provider = OllamaProvider(base_url="http://127.0.0.1:11434", model="gemma4:e2b")
    
    with patch("requests.get") as mock_get, patch("requests.post") as mock_post:
        # Mock tags
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "models": [{"name": "gemma4:e2b:latest"}]
        }
        
        # Mock generate
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "response": "Generated local bullet."
        }
        
        assert provider.is_available() is True
        assert provider.is_model_installed("gemma4:e2b") is True
        
        result = provider.generate_text("Generate resume bullet", model_hint="test")
        assert result == "Generated local bullet."


def test_ai_gateway_auto_routes_to_local_when_ready():
    mock_local = MagicMock(spec=OllamaProvider)
    mock_local.is_available.return_value = True
    mock_local.is_model_installed.return_value = True
    mock_local.generate_text.return_value = "Local response"

    mock_cloud = MagicMock(spec=GeminiProvider)
    mock_cloud.is_available.return_value = True

    config = AIConfig(mode="auto", local_model="gemma4:e2b", cloud_fallback=True)
    gateway = AIGateway(config=config, local_provider=mock_local, cloud_provider=mock_cloud)

    provider, desc = gateway.resolve_provider()
    assert provider == mock_local
    assert "Local" in desc

    output = gateway.generate_text("prompt")
    assert output == "Local response"
    mock_local.generate_text.assert_called_once()
    mock_cloud.generate_text.assert_not_called()


def test_ai_gateway_auto_falls_back_to_cloud_when_local_offline():
    mock_local = MagicMock(spec=OllamaProvider)
    mock_local.is_available.return_value = False

    mock_cloud = MagicMock(spec=GeminiProvider)
    mock_cloud.is_available.return_value = True
    mock_cloud.generate_text.return_value = "Cloud fallback response"

    config = AIConfig(mode="auto", cloud_fallback=True)
    gateway = AIGateway(config=config, local_provider=mock_local, cloud_provider=mock_cloud)

    provider, desc = gateway.resolve_provider()
    assert "Cloud" in desc

    output = gateway.generate_text("prompt")
    assert output == "Cloud fallback response"
    mock_cloud.generate_text.assert_called_once()


def test_ai_gateway_forced_local_errors_if_offline():
    mock_local = MagicMock(spec=OllamaProvider)
    mock_local.is_available.return_value = False

    config = AIConfig(mode="local")
    gateway = AIGateway(config=config, local_provider=mock_local)

    with pytest.raises(RuntimeError) as exc:
        gateway.resolve_provider()
    assert "Local mode is forced" in str(exc.value)


def test_ai_gateway_get_status():
    mock_local = MagicMock(spec=OllamaProvider)
    mock_local.is_available.return_value = True
    mock_local.list_models.return_value = ["gemma4:e2b"]
    mock_local.is_model_installed.return_value = True

    mock_cloud = MagicMock(spec=GeminiProvider)
    mock_cloud.is_available.return_value = False

    config = AIConfig(mode="auto", local_model="gemma4:e2b")
    gateway = AIGateway(config=config, local_provider=mock_local, cloud_provider=mock_cloud)

    status = gateway.get_status()
    assert status["mode"] == "auto"
    assert status["local_online"] is True
    assert status["local_model_ready"] is True
    assert status["cloud_ready"] is False
    assert "Local (gemma4:e2b)" in status["active_route"]
