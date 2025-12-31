from typing import Any, Callable, Dict, Optional

import hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Creates a full URL for a public REST API endpoint.
    """
    base_url = CONSTANTS.TESTNET_BASE_URL if "testnet" in domain else CONSTANTS.PERPETUAL_BASE_URL
    return f"{base_url}{path_url}"


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Creates a full URL for a private REST API endpoint.
    """
    return public_rest_url(path_url, domain)


def wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Creates a WebSocket URL.
    """
    return CONSTANTS.TESTNET_WS_URL if "testnet" in domain else CONSTANTS.PERPETUAL_WS_URL


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    domain: str = CONSTANTS.DOMAIN,
    time_provider: Optional[Callable] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Build the API factory for REST and WebSocket connections.
    """
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: time_synchronizer.time())

    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Build API factory without time synchronizer pre-processor.
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    """
    Creates an AsyncThrottler instance with the configured rate limits.
    """
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
) -> float:
    """
    Fetches the current server time from Aevo API.
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()

    url = public_rest_url(path_url=CONSTANTS.TIME_URL, domain=domain)

    response = await rest_assistant.execute_request(
        url=url,
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.TIME_URL,
    )

    server_time = float(response.get("timestamp", 0)) / 1e9
    return server_time


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Validates exchange information response.
    """
    return exchange_info is not None and len(exchange_info) > 0
