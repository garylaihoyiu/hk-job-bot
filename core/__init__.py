import asyncio

groq_semaphore = asyncio.Semaphore(3)
_user_locks: dict[int, asyncio.Lock] = {}


def get_user_lock(telegram_id: int) -> asyncio.Lock:
    if telegram_id not in _user_locks:
        _user_locks[telegram_id] = asyncio.Lock()
    return _user_locks[telegram_id]
