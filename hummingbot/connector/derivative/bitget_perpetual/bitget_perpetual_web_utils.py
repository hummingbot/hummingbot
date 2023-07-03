from typing import Callable, Dict, Optional

from hummingbot.connector.derivative.bitget_perpetual import bitget_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = None) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Bitget domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return get_rest_url_for_endpoint(path_url, domain)


def private_rest_url(path_url: str, domain: str = None) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Bitget domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return get_rest_url_for_endpoint(path_url, domain)


def get_rest_url_for_endpoint(endpoint: Dict[str, str], domain: str = None):
    return CONSTANTS.REST_URL + endpoint


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
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
    return throttler


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None, domain: str = ""
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    url = public_rest_url(path_url=CONSTANTS.SERVER_TIME_PATH_URL)
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
        method=RESTMethod.GET,
        return_err=True,
    )
    server_time = float(response["requestTime"])

    return server_time
