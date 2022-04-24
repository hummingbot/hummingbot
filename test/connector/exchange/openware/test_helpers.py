import asyncio
from typing_extensions import Awaitable


def async_run_with_timeout(coroutine: Awaitable, timeout: float = 1):
    ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
    return ret
