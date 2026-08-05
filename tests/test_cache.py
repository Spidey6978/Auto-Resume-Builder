import os
import tempfile
import gc
import pytest
from arb.core.cache import CacheManager


@pytest.fixture
def temp_cache():
    """Provides a temporary CacheManager with a clean SQLite DB per test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_cache.db")
        cm = CacheManager(db_path=db_path)
        yield cm
        gc.collect()


def test_cache_set_and_get(temp_cache):
    temp_cache.set("test_ns", "key_1", {"foo": "bar"})
    val = temp_cache.get("test_ns", "key_1")
    assert val == {"foo": "bar"}


def test_cache_miss_returns_none(temp_cache):
    val = temp_cache.get("test_ns", "non_existent_key")
    assert val is None


def test_cache_etag_storage_and_retrieval(temp_cache):
    temp_cache.set("github_api", "https://api.github.com/test", {"data": 123}, etag='"abc123etag"')
    result = temp_cache.get_with_meta("github_api", "https://api.github.com/test")

    assert result is not None
    payload, etag = result
    assert payload == {"data": 123}
    assert etag == '"abc123etag"'


def test_namespace_isolation(temp_cache):
    temp_cache.set("ns_a", "same_key", "value_a")
    temp_cache.set("ns_b", "same_key", "value_b")

    assert temp_cache.get("ns_a", "same_key") == "value_a"
    assert temp_cache.get("ns_b", "same_key") == "value_b"


def test_clear_namespace_and_all(temp_cache):
    temp_cache.set("ns_a", "k1", "val1")
    temp_cache.set("ns_b", "k2", "val2")

    temp_cache.clear("ns_a")
    assert temp_cache.get("ns_a", "k1") is None
    assert temp_cache.get("ns_b", "k2") == "val2"

    temp_cache.clear()
    assert temp_cache.get("ns_b", "k2") is None


def test_stable_hash_key():
    hash1 = CacheManager.hash_key("hello world")
    hash2 = CacheManager.hash_key("hello world")
    hash3 = CacheManager.hash_key("hello world!")

    assert hash1 == hash2
    assert hash1 != hash3
