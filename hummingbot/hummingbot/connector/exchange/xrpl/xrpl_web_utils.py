import time
from typing import Optional

import hummingbot.connector.exchange.cube.cube_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    return time.time()
