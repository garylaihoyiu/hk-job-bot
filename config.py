import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]
DATABASE_URL: str = os.environ["DATABASE_URL"]
DEFAULT_SEARCH_INTERVAL_HOURS: int = int(os.getenv("DEFAULT_SEARCH_INTERVAL_HOURS", "24"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
