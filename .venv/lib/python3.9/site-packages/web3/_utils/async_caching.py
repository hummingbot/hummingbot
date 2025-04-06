import asyncio
from concurrent.futures import (
    ThreadPoolExecutor,
)
import contextlib
import threading
from typing import (
    AsyncGenerator,
)


@contextlib.asynccontextmanager
async def async_lock(
    thread_pool: ThreadPoolExecutor, lock: threading.Lock
) -> AsyncGenerator[None, None]:
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(thread_pool, lock.acquire)
        yield
    finally:
        if lock.locked():
            lock.release()
