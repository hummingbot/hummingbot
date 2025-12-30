from typing import Callable, Optional

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_ws_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """WebSocket URL for Backpack Exchange."""
    return CONSTANTS.WSS_URL


def private_ws_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Private WebSocket URL (same as public for Backpack)."""
    return CONSTANTS.WSS_URL


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Build public REST API URL."""
    return f"{CONSTANTS.REST_URL}{path_url}"


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Build private REST API URL."""
    return f"{CONSTANTS.REST_URL}{path_url}"


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    return WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(
                synchronizer=time_synchronizer,
                time_provider=time_provider
            ),
        ],
    )


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler
) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler)


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    url = public_rest_url(path_url=CONSTANTS.PUBLIC_TIME_ENDPOINT, domain=domain)
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=CONSTANTS.PUBLIC_TIME_ENDPOINT,
        method=RESTMethod.GET,
        return_err=True,
    )
    # Backpack returns serverTime in milliseconds
    return float(response.get("serverTime", 0)) / 1000.0
