import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# APScheduler requires a synchronous engine — strip async driver prefix
_sync_db_url = (
    DATABASE_URL
    .replace("+asyncpg", "")
    .replace("+aiosqlite", "")
)

_jobstores = {
    "default": SQLAlchemyJobStore(url=_sync_db_url, tablename="apscheduler_jobs")
}

scheduler = AsyncIOScheduler(jobstores=_jobstores)

# Module-level bot reference set at startup — needed by APScheduler jobs (lambdas not picklable)
_bot = None


def set_bot(bot) -> None:
    global _bot
    _bot = bot


async def run_scheduled_search(telegram_id: int) -> None:
    """Top-level picklable function used by APScheduler job store."""
    from core.search_pipeline import run_search_for_user
    if _bot is None:
        logger.error("Bot not initialised — cannot run scheduled search")
        return
    await run_search_for_user(telegram_id, _bot, cooldown_check=False)


def add_user_search_job(telegram_id: int, interval_hours: int) -> None:
    job_id = f"search_{telegram_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(
        run_scheduled_search,
        trigger="interval",
        hours=interval_hours,
        id=job_id,
        args=[telegram_id],
        replace_existing=True,
        misfire_grace_time=3600,
    )
    logger.info(f"Scheduled search for user {telegram_id} every {interval_hours}h")


def remove_user_search_job(telegram_id: int) -> None:
    job_id = f"search_{telegram_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Removed search job for user {telegram_id}")
