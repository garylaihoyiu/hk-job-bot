# HK Job Finder Telegram Bot

A Telegram bot that matches your CV to Hong Kong job listings using Groq AI (free tier). Searches JobsDB, Indeed HK, and CTJobs automatically on your schedule.

## Features

- Upload your CV as PDF or DOCX
- AI extracts your skills, job titles, and experience
- Searches 3 Hong Kong job boards
- Scores each job for relevance (1–10) and notifies you of matches ≥ 7
- Per-user configurable search schedule (every 6h, 12h, or daily)
- Multi-user support — share with friends
- 100% free tier (Groq API + Railway.app + Railway PostgreSQL)

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message and instructions |
| `/upload` | Upload your CV (PDF or DOCX) |
| `/search` | Search for matching jobs now |
| `/schedule` | Set automatic search interval |
| `/profile` | View your extracted CV profile |
| `/results` | See your latest job matches |
| `/clear` | Reset all your data |

## Local Development

### Prerequisites

- Python 3.11+
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Groq API key from [console.groq.com](https://console.groq.com) (free, no credit card)
- A PostgreSQL database (or use SQLite for local dev by changing `DATABASE_URL`)

### Setup

```bash
# Clone and enter the project
cd hk-job-bot

# Install dependencies
pip install -r requirements.txt

# Copy env template and fill in your values
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and GROQ_API_KEY

# For local dev, set DATABASE_URL to SQLite:
# DATABASE_URL=sqlite+aiosqlite:///./jobbot.db

# Run the bot
python main.py
```

### Running Tests

```bash
python -m pytest tests/ -v
```

## Railway Deployment

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) and create a new project from your GitHub repo
3. In the Railway dashboard:
   - Add a **PostgreSQL** plugin (free, persistent)
   - The `DATABASE_URL` environment variable is automatically injected
4. Add these environment variables in Railway settings:
   - `TELEGRAM_BOT_TOKEN` — from @BotFather
   - `GROQ_API_KEY` — from console.groq.com
5. Railway uses the `Procfile` (`worker: python main.py`) — no further config needed
6. Deploy and your bot is live 24/7

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | From @BotFather on Telegram |
| `GROQ_API_KEY` | Yes | From console.groq.com (free) |
| `DATABASE_URL` | Yes | PostgreSQL URL (auto-injected by Railway) |
| `DEFAULT_SEARCH_INTERVAL_HOURS` | No | Default: 24 |
| `LOG_LEVEL` | No | Default: INFO |

## Architecture

```
bot/          Telegram handlers and keyboard layouts
core/         CV parser, job scrapers, job matcher, scheduler, search pipeline
db/           SQLModel database models and CRUD functions
main.py       Entry point — starts bot (long-polling) + APScheduler
```

## HK-Specific Notes

- All job searches are scoped to Hong Kong
- Uses Groq API (HK-accessible) — not Anthropic or OpenAI
- JobsDB is the primary source; Indeed HK and CTJobs are secondary
- Supports both English and Chinese job listings
