import pytest
from db.crud import (
    get_or_create_user, save_cv_profile, get_user,
    make_job_hash, is_job_seen, save_seen_job, get_recent_jobs,
    should_scrape, update_scrape_cache, clear_user,
)


@pytest.mark.asyncio
async def test_get_or_create_user_creates(db_session):
    user = await get_or_create_user(db_session, telegram_id=123)
    assert user.telegram_id == 123


@pytest.mark.asyncio
async def test_get_or_create_user_idempotent(db_session):
    u1 = await get_or_create_user(db_session, telegram_id=123)
    u2 = await get_or_create_user(db_session, telegram_id=123)
    assert u1.telegram_id == u2.telegram_id


@pytest.mark.asyncio
async def test_save_cv_profile(db_session):
    await get_or_create_user(db_session, telegram_id=1)
    user = await save_cv_profile(db_session, 1, "cv text", '{"skills": ["Python"]}')
    assert user.cv_text == "cv text"
    assert user.last_cv_uploaded_at is not None


@pytest.mark.asyncio
async def test_job_hash_stable(db_session):
    h1 = make_job_hash("HSBC", "Python Dev", "2026-05-01")
    h2 = make_job_hash("HSBC", "Python Dev", "2026-05-01")
    assert h1 == h2


@pytest.mark.asyncio
async def test_job_hash_different_for_different_jobs(db_session):
    h1 = make_job_hash("HSBC", "Python Dev", "2026-05-01")
    h2 = make_job_hash("HSBC", "Java Dev", "2026-05-01")
    assert h1 != h2


@pytest.mark.asyncio
async def test_save_seen_job_new(db_session):
    await get_or_create_user(db_session, telegram_id=1)
    job = {"job_hash": "abc123", "url": "http://x.com", "title": "Dev", "company": "Co", "score": 8, "reason": "good"}
    saved = await save_seen_job(db_session, 1, job)
    assert saved is True


@pytest.mark.asyncio
async def test_save_seen_job_duplicate(db_session):
    await get_or_create_user(db_session, telegram_id=1)
    job = {"job_hash": "abc123", "url": "http://x.com", "title": "Dev", "company": "Co", "score": 8, "reason": "good"}
    await save_seen_job(db_session, 1, job)
    saved_again = await save_seen_job(db_session, 1, job)
    assert saved_again is False


@pytest.mark.asyncio
async def test_should_scrape_new_entry(db_session):
    await get_or_create_user(db_session, telegram_id=1)
    result = await should_scrape(db_session, 1, "jobsdb", "python")
    assert result is True


@pytest.mark.asyncio
async def test_should_scrape_after_update(db_session):
    await get_or_create_user(db_session, telegram_id=1)
    await update_scrape_cache(db_session, 1, "jobsdb", "python")
    result = await should_scrape(db_session, 1, "jobsdb", "python")
    assert result is False


@pytest.mark.asyncio
async def test_clear_user_removes_data(db_session):
    await get_or_create_user(db_session, telegram_id=1)
    await save_cv_profile(db_session, 1, "cv text", '{"skills": []}')
    await clear_user(db_session, 1)
    user = await get_user(db_session, 1)
    assert user.cv_text is None
    assert user.profile_json is None
