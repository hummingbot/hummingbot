from typing import Callable, Optional
from urllib.parse import urljoin

import hummingbot.connector.exchange.vest.vest_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = None, environment: str = CONSTANTS.DEFAULT_ENVIRONMENT) -> str:
    """
    Creates a full URL for provided REST endpoint

    :param path_url: a public REST endpoint
    :param domain: The vest domain/environment (for compatibility with base class)
    :param environment: The environment (prod/dev)

    :return: the full URL to the endpoint
    """
    # If domain is provided, check if it's a full URL or environment name
    if domain is not None:
        if domain.startswith("https://"):
            # Domain is already a full URL, use it directly
            base_url = domain
        else:
            # Domain is an environment name, get the base URL
            base_url = CONSTANTS.get_vest_base_url(domain)
    else:
        base_url = CONSTANTS.get_vest_base_url(environment)
    return urljoin(base_url, path_url)


def private_rest_url(path_url: str, domain: str = None, environment: str = CONSTANTS.DEFAULT_ENVIRONMENT) -> str:
    """
    Creates a full URL for provided private REST endpoint

    :param path_url: a private REST endpoint
    :param domain: The vest domain/environment (for compatibility with base class)
    :param environment: The environment (prod/dev)

    :return: the full URL to the endpoint
    """
    return public_rest_url(path_url, domain, environment)


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
        domain: str = None,
        environment: str = CONSTANTS.DEFAULT_ENVIRONMENT) -> WebAssistantsFactory:
    # If domain is provided, check if it's a full URL or environment name
    if domain is not None:
        if not domain.startswith("https://"):
            # Domain is an environment name, use it
            environment = domain
        # If domain is a full URL, keep the original environment
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain,
        environment=environment
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
        domain: str = None,
        environment: str = CONSTANTS.DEFAULT_ENVIRONMENT) -> float:
    """
    Get current server time from Vest Markets API.
    Since Vest doesn't have a dedicated time endpoint, we'll use system time.

    Note: throttler, domain, and environment parameters are kept for API compatibility
    but not used in this implementation as we use system time.
    """
    import time
    return time.time() * 1000  # Return milliseconds like other exchanges
