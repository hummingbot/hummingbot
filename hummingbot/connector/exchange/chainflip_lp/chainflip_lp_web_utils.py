import time
from typing import Optional

import hummingbot.connector.exchange.chainflip_lp.chainflip_lp_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


<<<<<<< HEAD
=======
def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    return _time() * 1e3  # pragma: no cover


def _time() -> float:
<<<<<<< HEAD
    return time.time()  # pragma: no cover
=======
    return time.time()
>>>>>>> 67f0d8422 ((fix) fix code errors, format errors and test errors)
