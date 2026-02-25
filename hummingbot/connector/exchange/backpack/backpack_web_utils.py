"""Backpack web utilities."""
from typing import Optional

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Builds the full REST URL for public endpoints.
    
    :param path_url: The API path
    :param domain: The domain (default: "com")
    :return: Full URL
    """
    base_url = CONSTANTS.REST_URL
    return base_url + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Builds the full REST URL for private endpoints.
    
    :param path_url: The API path
    :param domain: The domain (default: "com")
    :return: Full URL
    """
    return public_rest_url(path_url, domain)


def ws_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Builds the WebSocket URL.
    
    :param domain: The domain (default: "com")
    :return: WebSocket URL
    """
    return CONSTANTS.WSS_URL + CONSTANTS.WS_PUBLIC_STREAM


def build_api_factory(
    throttler,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    """
    Builds a WebAssistantsFactory for Backpack API.
    
    :param throttler: The rate limit throttler
    :param time_synchronizer: Optional time synchronizer
    :param auth: Optional authentication object
    :return: WebAssistantsFactory instance
    """
    return WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
    )
