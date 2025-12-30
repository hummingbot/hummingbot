from typing import Optional

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
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
