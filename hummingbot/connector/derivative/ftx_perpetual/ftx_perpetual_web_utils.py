import time
from typing import Any, Dict, List, Optional

from hummingbot.connector.derivative.ftx_perpetual import ftx_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
    return throttler


def endpoint_from_message(message: Dict[str, Any]) -> Optional[str]:
    ...


def payload_from_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
    ...


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided REST endpoint

    :param path_url: a public REST endpoint
    :param domain: not required for OKX. Added only for compatibility.

    :return: the full URL to the endpoint
    """
    return CONSTANTS.FTX_BASE_URL + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return public_rest_url(path_url, domain)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN) -> float:
    # FTX does not provide an endpoint to get the server time
    return time.time()
