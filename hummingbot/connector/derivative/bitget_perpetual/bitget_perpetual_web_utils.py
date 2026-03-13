from typing import Callable, Optional
from urllib.parse import urljoin

from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_ws_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public websocket endpoint
    """
    return _create_ws_url(CONSTANTS.WSS_PUBLIC_ENDPOINT, domain)


def private_ws_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private websocket endpoint
    """
    return _create_ws_url(CONSTANTS.WSS_PRIVATE_ENDPOINT, domain)


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint

    :param path_url: a public REST endpoint
    :param domain: the Bitget domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return _create_rest_url(path_url, domain)


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint

    :param path_url: a private REST endpoint
    :param domain: the Bitget domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return _create_rest_url(path_url, domain)


def _create_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided REST endpoint

    :param path_url: a REST endpoint
    :param domain: the Bitget domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return urljoin(f"https://{CONSTANTS.REST_SUBDOMAIN}.{domain}", path_url)


def _create_ws_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided websocket endpoint

    :param path_url: a websocket endpoint
    :param domain: the Bitget domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return urljoin(f"wss://{CONSTANTS.WSS_SUBDOMAIN}.{domain}", path_url)


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(
                synchronizer=time_synchronizer,
                time_provider=time_provider
            ),
        ],
    )

    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler
) -> WebAssistantsFactory:
    """
    Build an API factory without the time synchronizer pre-processor.

    :param throttler: The throttler to use for the API factory.
    :return: The API factory.
    """
    api_factory = WebAssistantsFactory(throttler=throttler)

    return api_factory


def create_throttler() -> AsyncThrottler:
    """
    Create a throttler with the default rate limits.

    :return: The throttler.
    """
    throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

    return throttler


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN
) -> float:
    """
    Get the current server time in seconds.

    :param throttler: The throttler to use for the request.
    :param domain: The domain to use for the request.
    :return: The current server time in seconds.
    """
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
    server_time = float(response["requestTime"])

    return server_time
