import os
import tempfile
import gc
import pytest
from unittest.mock import patch, MagicMock
from adapters.github_adapter import GitHubAdapter
from core.cache import CacheManager


@pytest.fixture
def temp_cache():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_gh_cache.db")
        cm = CacheManager(db_path=db_path)
        yield cm
        gc.collect()


def test_github_adapter_etag_conditional_request_304(temp_cache):
    adapter = GitHubAdapter(token="fake_token", cache_manager=temp_cache)
    url = "https://api.github.com/repos/testowner/testrepo"

    # Seed the cache with initial data and an ETag
    initial_payload = {"name": "testrepo", "description": "initial description"}
    temp_cache.set(adapter.CACHE_NAMESPACE, url, initial_payload, etag='"etag_v1"')

    # Mock requests.get to return 304 Not Modified
    mock_resp = MagicMock()
    mock_resp.status_code = 304

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = adapter._get_url(url)

        # Verify ETag was sent in headers
        called_headers = mock_get.call_args[1]["headers"]
        assert called_headers.get("If-None-Match") == '"etag_v1"'
        # Verify cached payload was returned on 304
        assert result == initial_payload


def test_github_adapter_etag_conditional_request_200_update(temp_cache):
    adapter = GitHubAdapter(token="fake_token", cache_manager=temp_cache)
    url = "https://api.github.com/repos/testowner/testrepo"

    # Seed initial cache
    temp_cache.set(adapter.CACHE_NAMESPACE, url, {"name": "old"}, etag='"etag_v1"')

    # Mock 200 OK response with new data and new ETag
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"ETag": '"etag_v2"'}
    mock_resp.json.return_value = {"name": "new_name", "description": "updated"}

    with patch("requests.get", return_value=mock_resp):
        result = adapter._get_url(url)
        assert result == {"name": "new_name", "description": "updated"}

        # Verify new ETag stored in cache
        cached_payload, cached_etag = temp_cache.get_with_meta(adapter.CACHE_NAMESPACE, url)
        assert cached_payload == {"name": "new_name", "description": "updated"}
        assert cached_etag == '"etag_v2"'


def test_github_adapter_401_fallback_unauthenticated(temp_cache):
    adapter = GitHubAdapter(token="invalid_token", cache_manager=temp_cache)
    url = "https://api.github.com/repos/testowner/public_repo"

    # Mock first GET returning 401, second GET (unauthenticated) returning 200 OK
    resp_401 = MagicMock()
    resp_401.status_code = 401

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.headers = {}
    resp_200.json.return_value = {"name": "public_repo"}

    with patch("requests.get", side_effect=[resp_401, resp_200]):
        result = adapter._get_url(url)
        assert result == {"name": "public_repo"}
