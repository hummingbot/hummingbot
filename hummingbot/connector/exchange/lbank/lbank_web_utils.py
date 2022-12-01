from typing import Callable, Optional

from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, api_version: str = CONSTANTS.API_VERSION, **_kwargs) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param api_version: the LBank API version to connect to ("v1", "v2"). The default value is "v2"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.LBANK_REST_URL + api_version + path_url


def private_rest_url(path_url: str, api_version: str = CONSTANTS.API_VERSION, **_kwargs) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param api_version: the LBank API version to connect to ("v1", "v2"). The default value is "v2"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.LBANK_REST_URL + api_version + path_url


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        **kwargs) -> float:
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.LBANK_GET_TIMESTAMP_PATH_URL),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.LBANK_GET_TIMESTAMP_PATH_URL,
    )
    server_time = int(response["data"])

    return server_time


def build_api_factory(
    auth: Optional[AuthBase] = None,
    throttler: Optional[AsyncThrottler] = None,
    time_provider: Optional[Callable] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        auth=auth,
        throttler=throttler,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider)
        ],
    )
    return api_factory
