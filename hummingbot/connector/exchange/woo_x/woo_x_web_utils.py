import time
from typing import Callable, Optional

import hummingbot.connector.exchange.woo_x.woo_x_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Woo X domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URLS[domain] + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return public_rest_url(path_url, domain)


def wss_public_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.WSS_PUBLIC_URLS[domain]


def wss_private_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    return CONSTANTS.WSS_PRIVATE_URLS[domain]


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    time_provider: Optional[Callable] = None,
    auth: Optional[AuthBase] = None
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()

    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth
    )

    return api_factory


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    return time.time() * 1e3


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)
