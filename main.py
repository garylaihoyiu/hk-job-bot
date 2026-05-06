import logging
import asyncio
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters,
)
from config import TELEGRAM_BOT_TOKEN, LOG_LEVEL
from bot.handlers import (
    start, upload, handle_document, search,
    profile, schedule_cmd, schedule_callback,
    results, clear_cmd, clear_callback,
)
from core.scheduler import scheduler, set_bot
from db import init_db

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    await init_db()
    logger.info("Database initialised")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register bot reference so APScheduler jobs can send Telegram messages
    set_bot(app.bot)

    scheduler.start()
    logger.info("Scheduler started")

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upload", upload))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("schedule", schedule_cmd))
    app.add_handler(CommandHandler("results", results))
    app.add_handler(CommandHandler("clear", clear_cmd))

    # Document upload handler
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Inline keyboard callbacks
    app.add_handler(CallbackQueryHandler(schedule_callback, pattern="^schedule_"))
    app.add_handler(CallbackQueryHandler(clear_callback, pattern="^(confirm|cancel)_clear$"))

    logger.info("Bot starting (long-polling)...")
    try:
        await app.run_polling()
    finally:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
