import time
from typing import Optional

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Build REST API URL for the given path.

    Args:
        path_url: The API endpoint path
        domain: Exchange domain (mainnet or testnet)

    Returns:
        Full REST API URL
    """
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return f"{CONSTANTS.TESTNET_BASE_URL}{path_url}"
    return f"{CONSTANTS.BASE_URL}{path_url}"


def public_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return rest_url(path_url=path_url, domain=domain)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    return rest_url(path_url=path_url, domain=domain)


def wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    """
    Build WebSocket URL for the given domain.

    Args:
        domain: Exchange domain (mainnet or testnet)

    Returns:
        WebSocket URL
    """
    if domain == CONSTANTS.TESTNET_DOMAIN:
        return CONSTANTS.TESTNET_WS_URL
    return CONSTANTS.WS_URL


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Build the API factory for making REST and WebSocket requests.

    Args:
        throttler: Rate limiter
        auth: Authentication handler

    Returns:
        WebAssistantsFactory instance
    """
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    """
    Build the API factory without time synchronizer (for public endpoints).

    Args:
        throttler: Rate limiter

    Returns:
        WebAssistantsFactory instance
    """
    return WebAssistantsFactory(throttler=throttler)


def create_throttler() -> AsyncThrottler:
    """
    Create a throttler with the default rate limits.

    Returns:
        AsyncThrottler instance
    """
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DOMAIN,
) -> float:
    """
    Fetch current server time from Backpack API.

    Args:
        throttler: Rate limiter instance
        domain: The domain name

    Returns:
        Server timestamp as float (milliseconds)
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.TIME_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.TIME_URL,
    )

    server_time = None
    if isinstance(response, dict):
        for key in ("serverTime", "server_time", "time", "timestamp", "ts"):
            if key in response:
                server_time = response[key]
                break
    else:
        server_time = response

    try:
        server_time = float(server_time)
    except Exception:
        server_time = time.time() * 1e3

    # Normalize to milliseconds
    if server_time > 1e14:
        server_time /= 1000.0
    elif server_time < 1e11:
        server_time *= 1000.0

    return server_time
