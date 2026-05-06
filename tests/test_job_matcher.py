import os
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

import pytest
from unittest.mock import AsyncMock, patch

from core.job_matcher import score_job, score_jobs_batch

PROFILE = '{"job_titles": ["Python Developer"], "skills": ["Python", "Django"], "experience_years": 3, "education": "BSc CS", "languages": ["English"]}'
JOB = {"title": "Senior Python Developer", "company": "HSBC", "url": "http://x.com", "date_posted": "2026-05-01", "source": "jobsdb"}


def _mock_response(content: str):
    return type("R", (), {
        "choices": [type("C", (), {
            "message": type("M", (), {"content": content})()
        })()]
    })()


@pytest.mark.asyncio
async def test_score_job_returns_high_score():
    mock_content = '{"score": 9, "reason": "Strong Python match"}'
    with patch("core.job_matcher.groq_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_response(mock_content))
        result = await score_job(PROFILE, JOB)
    assert result is not None
    assert result["score"] == 9
    assert "reason" in result


@pytest.mark.asyncio
async def test_score_job_returns_none_on_bad_json():
    with patch("core.job_matcher.groq_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_response("bad json"))
        result = await score_job(PROFILE, JOB)
    assert result is None


@pytest.mark.asyncio
async def test_score_job_clamps_score_above_10():
    mock_content = '{"score": 15, "reason": "Way too high"}'
    with patch("core.job_matcher.groq_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_response(mock_content))
        result = await score_job(PROFILE, JOB)
    assert result["score"] == 10


@pytest.mark.asyncio
async def test_score_jobs_batch_filters_by_threshold():
    scores = [
        '{"score": 9, "reason": "Great match"}',
        '{"score": 4, "reason": "Poor match"}',
    ]
    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        content = scores[call_count]
        call_count += 1
        return _mock_response(content)

    jobs = [JOB, {**JOB, "title": "Unrelated Marketing Role"}]
    with patch("core.job_matcher.groq_client") as mock_client:
        mock_client.chat.completions.create = mock_create
        results = await score_jobs_batch(PROFILE, jobs, threshold=7)

    assert len(results) == 1
    assert results[0]["score"] == 9


@pytest.mark.asyncio
async def test_score_jobs_batch_caps_at_50():
    mock_content = '{"score": 8, "reason": "match"}'
    jobs = [JOB] * 60
    with patch("core.job_matcher.groq_client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=_mock_response(mock_content))
        results = await score_jobs_batch(PROFILE, jobs, threshold=7)
    assert mock_client.chat.completions.create.call_count <= 50
