import logging
import asyncio
from config import LOG_LEVEL

logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)


async def main():
    logger.info("Bot starting...")


if __name__ == "__main__":
    asyncio.run(main())
