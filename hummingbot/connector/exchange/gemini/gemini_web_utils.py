from typing import Callable, Optional

import hummingbot.connector.exchange.gemini.gemini_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = "") -> str:
    return CONSTANTS.REST_URL + path_url


def private_rest_url(path_url: str, domain: str = "") -> str:
    return CONSTANTS.REST_URL + path_url


def wss_url() -> str:
    return CONSTANTS.WSS_URL


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = "",
) -> float:
    """Fetch server time from Gemini's API response Date header.
    This ensures nonces stay valid even when the local clock (e.g., Podman VM) drifts."""
    import logging
    import time
    logger = logging.getLogger(__name__)
    for attempt in range(3):
        try:
            from email.utils import parsedate_to_datetime

            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.head(CONSTANTS.REST_URL + "/v1/symbols", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    date_str = response.headers.get("Date", "")
                    if date_str:
                        server_dt = parsedate_to_datetime(date_str)
                        return server_dt.timestamp() * 1e3
        except Exception as e:
            if attempt < 2:
                import asyncio
                await asyncio.sleep(0.5)
            else:
                logger.warning(f"Failed to fetch Gemini server time after 3 attempts ({e}), "
                               f"falling back to local clock (may cause nonce errors if VM clock is drifted)")
    return time.time() * 1e3
