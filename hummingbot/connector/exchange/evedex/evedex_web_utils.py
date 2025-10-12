from typing import Callable, Optional

import hummingbot.connector.exchange.evedex.evedex_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint.

    :param path_url: a public REST endpoint
    :param domain: the domain (not used currently, kept for consistency)
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint.

    :param path_url: a private REST endpoint
    :param domain: the domain (not used currently, kept for consistency)
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL + path_url


def wss_public_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Returns the WebSocket URL for public streams."""
    return "wss://exchange-api.evedex.com/ws/public"


def wss_private_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """Returns the WebSocket URL for private streams."""
    return "wss://exchange-api.evedex.com/ws/private"


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN) -> WebAssistantsFactory:
    """
    Builds and returns a WebAssistantsFactory instance configured for EVEDEX.

    :param throttler: the rate limiter to use
    :param time_synchronizer: the time synchronizer to use
    :param time_provider: a callable that returns the current server time
    :param auth: the authenticator to use for private requests
    :param domain: the domain (not used currently, kept for consistency)
    :return: a configured WebAssistantsFactory instance
    """
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(
        throttler=throttler,
        domain=domain
    ))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ])
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
        throttler: AsyncThrottler) -> WebAssistantsFactory:
    """
    Builds a WebAssistantsFactory without time synchronizer pre-processor.
    Used for fetching server time.

    :param throttler: the rate limiter to use
    :return: a configured WebAssistantsFactory instance
    """
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    """
    Creates and returns an AsyncThrottler configured with EVEDEX rate limits.

    :return: a configured AsyncThrottler instance
    """
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN) -> float:
    """
    Fetches the current server time from EVEDEX.

    :param throttler: the rate limiter to use
    :param domain: the domain (not used currently, kept for consistency)
    :return: the current server time in milliseconds
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.SERVER_TIME_PATH,
    )

    server_time = response.get("time") if isinstance(response, dict) else None

    if server_time is None:
        raise RuntimeError("Unexpected response format when retrieving EVEDEX server time.")

    server_time = float(server_time)
    return server_time * 1e-3 if server_time > 1e12 else server_time
