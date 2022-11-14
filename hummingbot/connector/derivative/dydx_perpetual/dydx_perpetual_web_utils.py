from typing import Callable, Optional

import hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.DYDX_REST_URL + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Binance domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.DYDX_REST_URL + path_url


def build_api_factory(
    throttler: AsyncThrottler,
    time_synchronizer: TimeSynchronizer,
    auth: AuthBase,
    time_provider: Optional[Callable] = None,
) -> WebAssistantsFactory:
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ],
    )
    return api_factory


async def get_current_server_time(throttler: AsyncThrottler, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> float:
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    url = public_rest_url(CONSTANTS.PATH_TIME)
    limit_id = CONSTANTS.LIMIT_ID_GET
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=limit_id,
        method=RESTMethod.GET,
    )
    server_time = float(response["epoch"])

    return server_time


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory
