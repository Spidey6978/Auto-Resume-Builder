import os
import tempfile
import gc
import pytest
from unittest.mock import patch, MagicMock
from core.ai_gateway import AIGateway, classify_exception, PROMPT_VERSION
from core.cache import CacheManager


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


def test_ai_gateway_cache_hit_prevents_api_call(temp_cache):
    gateway = AIGateway(cache_manager=temp_cache)
    repo_name = "TestRepo"
    readme_content = "This is a full README content exceeding fifty characters for testing."

    # Manually compute key with PROMPT_VERSION & prompt hash
    context_type = "a technical repository"
    truncated = readme_content[:40000]
    prompt = f"""
        You are an elite ATS resume writer and senior engineering recruiter. I have {context_type} named '{repo_name}'.
        Here is the content of the README.md:
        
        {truncated}
        
        Your task: Generate exactly 2 professional, highly technical resume bullet points summarizing the architecture, logic, and impact of this project.
        Rules:
        - Analyze the entire README. Deeply extract the complex logic, math, physics, or architectural patterns used (ignore fluff and licenses).
        - Start each bullet with a strong, VARIED past-tense action verb (e.g., Architected, Designed, Orchestrated, Optimized, Spearheaded, Integrated). DO NOT repeat the same starting verb across bullets.
        - Quantify impact where possible and aggressively highlight the tech stack/frameworks.
        - Never invent compound architectural terms. Use precise standard terminology only.
        - DO NOT include markdown formatting like asterisks (*), bolding, or hyphens at the start.
        - STRICT LENGTH LIMIT: Keep each bullet punchy, around 15-25 words, so it fits exactly on a single line in a PDF.
        - Return ONLY the 2 bullet points, separated by a newline.
        """
    prompt_hash = CacheManager.hash_key(prompt)
    cache_key = f"{PROMPT_VERSION}||general||{prompt_hash}||{repo_name}||{truncated}"

    expected_bullets = ["Bullet 1 from cache", "Bullet 2 from cache"]
    temp_cache.set(gateway.CACHE_NAMESPACE, cache_key, expected_bullets)

    # Ensure no API calls are made
    with patch("google.generativeai.GenerativeModel") as mock_model:
        result = gateway.generate_bullets_from_readme(repo_name, readme_content)
        assert result == expected_bullets
        mock_model.assert_not_called()


def test_ai_gateway_insufficient_data_returns_failure_status(temp_cache):
    gateway = AIGateway(cache_manager=temp_cache)
    # Short README < 50 chars
    short_readme = "Too short"
    result = gateway.generate_bullets_from_readme("ShortRepo", short_readme)

    assert len(result) == 1
    assert "⚠️ Insufficient source material" in result[0]
