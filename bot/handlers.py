import json
import logging
from telegram import Update
from telegram.ext import ContextTypes
from db import AsyncSessionLocal
from db.crud import (
    get_or_create_user, save_cv_profile, get_user,
    update_search_schedule, get_recent_jobs, clear_user,
)
from bot.keyboards import schedule_keyboard, clear_confirm_keyboard
from core.cv_parser import extract_text_from_bytes, parse_cv_with_groq

logger = logging.getLogger(__name__)

# FSM states
IDLE = "IDLE"
AWAITING_CV = "AWAITING_CV"

# In-memory per-user state dict
_user_states: dict[int, str] = {}


def get_state(telegram_id: int) -> str:
    return _user_states.get(telegram_id, IDLE)


def set_state(telegram_id: int, state: str) -> None:
    _user_states[telegram_id] = state


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    async with AsyncSessionLocal() as session:
        await get_or_create_user(session, user.id, user.username)
    await update.message.reply_text(
        f"👋 Welcome to HK Job Finder, {user.first_name}!\n\n"
        "I'll search Hong Kong job boards for openings that match your CV.\n\n"
        "To get started:\n"
        "• /upload — Send your CV (PDF or DOCX)\n"
        "• /search — Search for jobs now\n"
        "• /schedule — Set up automatic searches\n"
        "• /results — See your latest matches\n"
        "• /profile — View your extracted CV profile\n"
        "• /clear — Reset everything"
    )


# ---------------------------------------------------------------------------
# /upload + document handler
# ---------------------------------------------------------------------------

async def upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    set_state(update.effective_user.id, AWAITING_CV)
    await update.message.reply_text("📄 Please send your CV as a PDF or DOCX file.")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if get_state(user_id) != AWAITING_CV:
        return

    doc = update.message.document
    if doc is None:
        return

    filename = doc.file_name or ""
    mime = doc.mime_type or ""
    allowed_extensions = (".pdf", ".docx")
    allowed_mimes = (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    if not (filename.lower().endswith(allowed_extensions) or mime in allowed_mimes):
        await update.message.reply_text(
            "❌ Please send a PDF or DOCX file. Other file types aren't supported."
        )
        return

    set_state(user_id, IDLE)
    await update.message.reply_text("⏳ Parsing your CV...")

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()
    except Exception as e:
        logger.error(f"File download failed for user {user_id}: {e}")
        await update.message.reply_text("❌ Couldn't download your file. Please try again.")
        return

    try:
        cv_text = extract_text_from_bytes(bytes(file_bytes), filename)
    except Exception as e:
        logger.error(f"CV text extraction failed for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Couldn't read your CV. The file may be corrupted. Please try again."
        )
        return

    try:
        profile_json = await parse_cv_with_groq(cv_text)
    except Exception as e:
        error_msg = str(e).lower()
        if "rate_limit" in error_msg or "429" in error_msg:
            await update.message.reply_text(
                "⚠️ AI rate limit hit. Please try /upload again in a minute."
            )
        elif "quota" in error_msg or "exceeded" in error_msg:
            await update.message.reply_text(
                "❌ Daily AI quota used up (resets midnight UTC). Please try again tomorrow."
            )
        else:
            await update.message.reply_text(
                "❌ AI service temporarily unavailable. Please try /upload again later."
            )
        return

    if profile_json is None:
        await update.message.reply_text(
            "⚠️ CV uploaded but AI couldn't extract a full profile. Please try /upload again."
        )
        return

    async with AsyncSessionLocal() as session:
        await save_cv_profile(session, user_id, cv_text, profile_json)

    await update.message.reply_text(
        "✅ CV parsed successfully! Use /profile to see your extracted profile, "
        "or /search to find matching jobs."
    )


# ---------------------------------------------------------------------------
# /profile
# ---------------------------------------------------------------------------

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        user = await get_user(session, user_id)

    if user is None or not user.profile_json:
        await update.message.reply_text(
            "❌ You haven't uploaded a CV yet. Use /upload to get started."
        )
        return

    p = json.loads(user.profile_json)
    uploaded = (
        user.last_cv_uploaded_at.strftime("%Y-%m-%d %H:%M UTC")
        if user.last_cv_uploaded_at
        else "Unknown"
    )
    lines = [
        "👤 *Your CV Profile*",
        f"📅 Last uploaded: {uploaded}",
        f"💼 Job titles: {', '.join(p.get('job_titles', []))}",
        f"🛠 Skills: {', '.join(p.get('skills', []))}",
        f"📆 Experience: {p.get('experience_years', '?')} years",
        f"🎓 Education: {p.get('education', 'N/A')}",
        f"🗣 Languages: {', '.join(p.get('languages', []))}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ---------------------------------------------------------------------------
# /search — delegates to search_pipeline (imported lazily to avoid circular)
# ---------------------------------------------------------------------------

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from core.search_pipeline import run_search_for_user
    await run_search_for_user(update.effective_user.id, context.bot)


# ---------------------------------------------------------------------------
# /schedule + callback
# ---------------------------------------------------------------------------

async def schedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🕒 How often should I search for new jobs?",
        reply_markup=schedule_keyboard(),
    )


async def schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    from core.scheduler import add_user_search_job, remove_user_search_job

    if data == "schedule_off":
        async with AsyncSessionLocal() as session:
            await update_search_schedule(session, user_id, 24, is_searching=False)
        remove_user_search_job(user_id)
        await query.edit_message_text("✅ Automatic job search turned off.")
        return

    interval_map = {"schedule_6": 6, "schedule_12": 12, "schedule_24": 24}
    hours = interval_map.get(data, 24)

    async with AsyncSessionLocal() as session:
        await update_search_schedule(session, user_id, hours, is_searching=True)

    add_user_search_job(user_id, hours)
    label = {6: "6 hours", 12: "12 hours", 24: "daily"}.get(hours, f"{hours}h")
    await query.edit_message_text(f"✅ I'll search for new jobs every {label}.")


# ---------------------------------------------------------------------------
# /results
# ---------------------------------------------------------------------------

async def results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    async with AsyncSessionLocal() as session:
        jobs = await get_recent_jobs(session, user_id, limit=5)

    if not jobs:
        await update.message.reply_text(
            "📭 No results yet. Use /search to find matching jobs."
        )
        return

    await update.message.reply_text("📋 *Your latest matches:*", parse_mode="Markdown")
    for job in jobs:
        await update.message.reply_text(
            f"📌 {job.job_title}\n"
            f"🏢 {job.company}\n"
            f"⭐ Match: {job.score}/10 — {job.score_reason}\n"
            f"🔗 {job.job_url}"
        )


# ---------------------------------------------------------------------------
# /clear + callback
# ---------------------------------------------------------------------------

async def clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "⚠️ This will delete your CV, profile, and all job history. Are you sure?",
        reply_markup=clear_confirm_keyboard(),
    )


async def clear_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "confirm_clear":
        from core.scheduler import remove_user_search_job
        async with AsyncSessionLocal() as session:
            await clear_user(session, user_id)
        remove_user_search_job(user_id)
        await query.edit_message_text("✅ All your data has been cleared. Start fresh with /upload.")
    else:
        await query.edit_message_text("Cancelled. Your data is safe.")
