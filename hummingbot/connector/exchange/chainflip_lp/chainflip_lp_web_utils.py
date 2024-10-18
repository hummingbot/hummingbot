import time
from typing import Optional

import hummingbot.connector.exchange.chainflip_lp.chainflip_lp_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    return _time() * 1e3  # pragma: no cover


def _time() -> float:
    return time.time()  # pragma: no cover
