import asyncio
import json
import logging
from groq import AsyncGroq
from config import GROQ_API_KEY
from core import groq_semaphore

logger = logging.getLogger(__name__)
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

_BATCH_CAP = 50
_SCORE_SYSTEM_PROMPT = (
    "You are a job relevance scorer. Given a candidate profile and a job posting, "
    "return ONLY valid JSON: {\"score\": <integer 1-10>, \"reason\": \"<brief reason>\"}. "
    "No markdown, no explanation."
)


async def score_job(profile_json: str, job: dict) -> dict | None:
    """Returns scored job dict or None if scoring fails."""
    description = f"{job['title']} at {job['company']}"
    user_prompt = (
        f"Candidate profile: {profile_json}\n\n"
        f"Job: {description}"
    )
    try:
        async with groq_semaphore:
            response = await groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": _SCORE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
            )
            await asyncio.sleep(2)

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        score = max(1, min(10, int(data["score"])))
        return {**job, "score": score, "reason": data.get("reason", "")}
    except json.JSONDecodeError:
        logger.warning(f"Bad JSON from Groq scoring: {job.get('title', '?')}")
        return None
    except Exception as e:
        logger.error(f"Groq scoring error: {e}")
        raise


async def score_jobs_batch(profile_json: str, jobs: list[dict], threshold: int = 7) -> list[dict]:
    """Score up to _BATCH_CAP jobs, return those with score >= threshold."""
    capped = jobs[:_BATCH_CAP]
    results = []
    for job in capped:
        try:
            scored = await score_job(profile_json, job)
            if scored and scored["score"] >= threshold:
                results.append(scored)
        except Exception as e:
            logger.error(f"Skipping job due to scoring error: {e}")
            continue
    return results
