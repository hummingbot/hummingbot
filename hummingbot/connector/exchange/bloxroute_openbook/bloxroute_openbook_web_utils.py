import time
from typing import Optional

from hummingbot.connector import constants
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = "",
) -> float:
    return time.time()
