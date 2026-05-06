import asyncio
import json
import logging
from datetime import datetime, timedelta
from telegram import Bot
from db import AsyncSessionLocal
from db.crud import (
    get_user, update_last_searched, save_seen_job,
    should_scrape, update_scrape_cache, make_job_hash, is_job_seen,
)
from core import get_user_lock
from core.job_scraper import scrape_jobsdb, scrape_indeed, scrape_ctjobs
from core.job_matcher import score_jobs_batch

logger = logging.getLogger(__name__)

SEARCH_COOLDOWN_MINUTES = 5


async def run_search_for_user(
    telegram_id: int, bot: Bot, cooldown_check: bool = True
) -> None:
    async with get_user_lock(telegram_id):
        async with AsyncSessionLocal() as session:
            user = await get_user(session, telegram_id)
            if user is None or not user.profile_json:
                await bot.send_message(
                    telegram_id,
                    "❌ You haven't uploaded a CV yet. Use /upload to get started.",
                )
                return

            if cooldown_check and user.last_searched_at:
                elapsed = datetime.utcnow() - user.last_searched_at
                if elapsed < timedelta(minutes=SEARCH_COOLDOWN_MINUTES):
                    remaining = SEARCH_COOLDOWN_MINUTES - int(elapsed.total_seconds() / 60)
                    await bot.send_message(
                        telegram_id,
                        f"⏳ Please wait {remaining} more minute(s) before searching again.",
                    )
                    return

            profile = json.loads(user.profile_json)
            queries = (profile.get("job_titles", []) + profile.get("skills", []))[:8]
            profile_json = user.profile_json

        await update_last_searched_safe(telegram_id)
        await bot.send_message(telegram_id, "🔍 Searching Hong Kong job boards...")

        all_jobs: list[dict] = []
        failed_sources: list[str] = []

        for query in queries:
            # JobsDB
            async with AsyncSessionLocal() as session:
                do_scrape = await should_scrape(session, telegram_id, "jobsdb", query)
            if do_scrape:
                jobs = await scrape_jobsdb(query)
                if not jobs:
                    failed_sources.append("JobsDB")
                all_jobs.extend(jobs)
                async with AsyncSessionLocal() as session:
                    await update_scrape_cache(session, telegram_id, "jobsdb", query)

            # Indeed HK
            async with AsyncSessionLocal() as session:
                do_scrape = await should_scrape(session, telegram_id, "indeed", query)
            if do_scrape:
                jobs = await scrape_indeed(query)
                if not jobs:
                    failed_sources.append("Indeed HK")
                all_jobs.extend(jobs)
                async with AsyncSessionLocal() as session:
                    await update_scrape_cache(session, telegram_id, "indeed", query)

            # CTJobs
            async with AsyncSessionLocal() as session:
                do_scrape = await should_scrape(session, telegram_id, "ctjobs", query)
            if do_scrape:
                jobs = await scrape_ctjobs(query)
                if not jobs:
                    failed_sources.append("CTJobs")
                all_jobs.extend(jobs)
                async with AsyncSessionLocal() as session:
                    await update_scrape_cache(session, telegram_id, "ctjobs", query)

        if not all_jobs:
            await bot.send_message(
                telegram_id,
                "⚠️ All job sources are currently unreachable. Will retry at next scheduled search.",
            )
            return

        # Deduplicate by hash
        seen_hashes: set[str] = set()
        unique_jobs: list[dict] = []
        for job in all_jobs:
            h = make_job_hash(job["company"], job["title"], job.get("date_posted", ""))
            if h not in seen_hashes:
                seen_hashes.add(h)
                job["job_hash"] = h
                unique_jobs.append(job)

        # Filter jobs already notified
        new_jobs: list[dict] = []
        async with AsyncSessionLocal() as session:
            for job in unique_jobs:
                if not await is_job_seen(session, telegram_id, job["job_hash"]):
                    new_jobs.append(job)

        if not new_jobs:
            await bot.send_message(
                telegram_id,
                "ℹ️ No new job listings since your last search. I'll keep checking.",
            )
            return

        # Score jobs with Groq
        try:
            matched = await score_jobs_batch(profile_json, new_jobs, threshold=7)
        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "429" in error_str:
                await bot.send_message(telegram_id, "⚠️ Groq API rate limit hit. Retrying in 60s...")
                await asyncio.sleep(60)
                try:
                    matched = await score_jobs_batch(profile_json, new_jobs, threshold=7)
                except Exception:
                    await bot.send_message(
                        telegram_id,
                        "❌ Rate limit persists. Try /search again in a few minutes.",
                    )
                    return
            elif "quota" in error_str or "exceeded" in error_str:
                await bot.send_message(
                    telegram_id,
                    "❌ Daily AI quota used up (resets midnight UTC). I'll try again at your next scheduled search.",
                )
                return
            else:
                await bot.send_message(
                    telegram_id,
                    "❌ AI service temporarily unavailable. Will retry at your next scheduled search.",
                )
                return

        if not matched:
            await bot.send_message(
                telegram_id,
                "🔎 No strong matches found this time (all jobs scored below 7/10). I'll keep checking.",
            )
            return

        # Save and notify — top 5
        for job in matched[:5]:
            async with AsyncSessionLocal() as session:
                saved = await save_seen_job(session, telegram_id, job)
            if saved:
                await bot.send_message(
                    telegram_id,
                    f"📌 {job['title']}\n"
                    f"🏢 {job['company']}\n"
                    f"⭐ Match: {job['score']}/10 — {job['reason']}\n"
                    f"🔗 {job['url']}",
                )

        if failed_sources:
            unique_failed = list(dict.fromkeys(failed_sources))
            await bot.send_message(
                telegram_id,
                f"ℹ️ Couldn't reach: {', '.join(unique_failed)}. Results from other sources included.",
            )


async def update_last_searched_safe(telegram_id: int) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await update_last_searched(session, telegram_id)
    except Exception as e:
        logger.warning(f"Could not update last_searched_at for {telegram_id}: {e}")
