import time
from typing import Callable, Optional

import hummingbot.connector.exchange.gemini.gemini_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    base = CONSTANTS.SANDBOX_REST_URL if "sandbox" in domain else CONSTANTS.REST_URL
    return base + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    base = CONSTANTS.SANDBOX_REST_URL if "sandbox" in domain else CONSTANTS.REST_URL
    return base + path_url


def wss_market_data_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.SANDBOX_WSS_MARKET_DATA_URL if "sandbox" in domain else CONSTANTS.WSS_MARKET_DATA_URL


def wss_order_events_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.SANDBOX_WSS_ORDER_EVENTS_URL if "sandbox" in domain else CONSTANTS.WSS_ORDER_EVENTS_URL


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
    ))
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
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    # Gemini does not have a dedicated server time endpoint.
    # Auth uses monotonically increasing nonces, so time sync is not critical.
    return time.time()
