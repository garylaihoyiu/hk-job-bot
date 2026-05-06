from datetime import datetime, timedelta
from typing import Optional
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from db.models import User, SeenJob, ScrapeCache


async def get_or_create_user(session: AsyncSession, telegram_id: int, username: Optional[str] = None) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def save_cv_profile(session: AsyncSession, telegram_id: int, cv_text: str, profile_json: str) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one()
    user.cv_text = cv_text
    user.profile_json = profile_json
    user.last_cv_uploaded_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(user)
    return user


async def get_user(session: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def update_search_schedule(
    session: AsyncSession, telegram_id: int, interval_hours: int, is_searching: bool
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one()
    user.search_interval_hours = interval_hours
    user.is_searching = is_searching
    user.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(user)
    return user


async def update_last_searched(session: AsyncSession, telegram_id: int) -> None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one()
    user.last_searched_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    await session.commit()


async def clear_user(session: AsyncSession, telegram_id: int) -> None:
    from sqlalchemy import delete
    await session.execute(delete(SeenJob).where(SeenJob.telegram_id == telegram_id))
    await session.execute(delete(ScrapeCache).where(ScrapeCache.telegram_id == telegram_id))
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user:
        user.cv_text = None
        user.profile_json = None
        user.is_searching = False
        user.last_searched_at = None
        user.last_cv_uploaded_at = None
        user.updated_at = datetime.utcnow()
    await session.commit()


def make_job_hash(company: str, title: str, date_posted: str) -> str:
    raw = f"{company.lower().strip()}{title.lower().strip()}{date_posted.strip()}"
    return hashlib.md5(raw.encode()).hexdigest()


async def is_job_seen(session: AsyncSession, telegram_id: int, job_hash: str) -> bool:
    result = await session.execute(
        select(SeenJob).where(SeenJob.telegram_id == telegram_id, SeenJob.job_hash == job_hash)
    )
    return result.scalar_one_or_none() is not None


async def save_seen_job(session: AsyncSession, telegram_id: int, job: dict) -> bool:
    """Returns True if saved (new job), False if already seen."""
    if await is_job_seen(session, telegram_id, job["job_hash"]):
        return False
    seen = SeenJob(
        telegram_id=telegram_id,
        job_hash=job["job_hash"],
        job_url=job["url"],
        job_title=job["title"],
        company=job["company"],
        score=max(1, min(10, int(job["score"]))),
        score_reason=job["reason"],
    )
    session.add(seen)
    try:
        await session.commit()
        return True
    except Exception:
        await session.rollback()
        return False


async def get_recent_jobs(session: AsyncSession, telegram_id: int, limit: int = 5) -> list[SeenJob]:
    result = await session.execute(
        select(SeenJob)
        .where(SeenJob.telegram_id == telegram_id)
        .order_by(SeenJob.notified_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def should_scrape(session: AsyncSession, telegram_id: int, site: str, query_key: str) -> bool:
    """Returns True if cache is missing or older than 1 hour."""
    result = await session.execute(
        select(ScrapeCache).where(
            ScrapeCache.telegram_id == telegram_id,
            ScrapeCache.site == site,
            ScrapeCache.query_key == query_key,
        )
    )
    cache = result.scalar_one_or_none()
    if cache is None:
        return True
    return (datetime.utcnow() - cache.last_scraped_at) > timedelta(hours=1)


async def update_scrape_cache(session: AsyncSession, telegram_id: int, site: str, query_key: str) -> None:
    result = await session.execute(
        select(ScrapeCache).where(
            ScrapeCache.telegram_id == telegram_id,
            ScrapeCache.site == site,
            ScrapeCache.query_key == query_key,
        )
    )
    cache = result.scalar_one_or_none()
    if cache is None:
        cache = ScrapeCache(telegram_id=telegram_id, site=site, query_key=query_key)
        session.add(cache)
    else:
        cache.last_scraped_at = datetime.utcnow()
    await session.commit()


async def get_all_searching_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.is_searching == True))
    return list(result.scalars().all())
