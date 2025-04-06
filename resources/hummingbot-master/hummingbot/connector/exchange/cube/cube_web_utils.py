import time
from typing import Optional

import hummingbot.connector.exchange.cube.cube_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.get(domain) + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.get(domain) + path_url


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(throttler=throttler, auth=auth)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> int:
    return int(time.time() * 1e3)
