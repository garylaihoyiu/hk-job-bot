import asyncio
import json
import logging
import google.generativeai as genai
from config import GEMINI_API_KEY
from core import groq_semaphore

logger = logging.getLogger(__name__)
genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-lite",
    generation_config=genai.GenerationConfig(temperature=0),
    system_instruction=(
        "You are a job relevance scorer. Given a candidate profile and a job posting, "
        "return ONLY valid JSON: {\"score\": <integer 1-10>, \"reason\": \"<brief reason>\"}. "
        "No markdown, no explanation."
    ),
)

_BATCH_CAP = 50


async def score_job(profile_json: str, job: dict) -> dict | None:
    """Returns scored job dict or None if scoring fails."""
    description = f"{job['title']} at {job['company']}"
    user_prompt = (
        f"Candidate profile: {profile_json}\n\n"
        f"Job: {description}"
    )
    try:
        async with groq_semaphore:
            response = await _model.generate_content_async(user_prompt)
            await asyncio.sleep(1)

        raw = response.text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        data = json.loads(raw)
        score = max(1, min(10, int(data["score"])))
        return {**job, "score": score, "reason": data.get("reason", "")}
    except json.JSONDecodeError:
        logger.warning(f"Bad JSON from Gemini scoring: {job.get('title', '?')}")
        return None
    except Exception as e:
        logger.error(f"Gemini scoring error: {e}")
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
