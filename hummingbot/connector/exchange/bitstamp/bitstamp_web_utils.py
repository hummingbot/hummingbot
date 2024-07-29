import json
from typing import Callable, Optional

import hummingbot.connector.exchange.bitstamp.bitstamp_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BitstampRESTPreProcessor(RESTPreProcessorBase):
    CONTENT_TYPE_HEADER = "Content-Type"

    async def pre_process(self, request: RESTRequest) -> RESTRequest:

        if not request.data and self.CONTENT_TYPE_HEADER in request.headers:
            # aiohttp adds the Content-Type header which is not allowed by bitstamp when sending an empty body.
            request.headers[self.CONTENT_TYPE_HEADER] = ''
            return request

        if request.method != RESTMethod.GET:
            request.headers[self.CONTENT_TYPE_HEADER] = "application/x-www-form-urlencoded"

            # rest_assistant converts the data dictionary to json but we need a urlencoded string instead
            # the actual url encoding of this is done by aiohttp.
            request.data = json.loads(request.data)

        return request


def public_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided public REST endpoint
    :param path_url: a public REST endpoint
    :param domain: the Bitstamp domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.API_VERSION + path_url


def private_rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Creates a full URL for provided private REST endpoint
    :param path_url: a private REST endpoint
    :param domain: the Bitstamp domain to connect to ("com" or "us"). The default value is "com"
    :return: the full URL to the endpoint
    """
    return CONSTANTS.REST_URL.format(domain) + CONSTANTS.API_VERSION + path_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        time_synchronizer: Optional[TimeSynchronizer] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
        time_provider: Optional[Callable] = None,
        auth: Optional[AuthBase] = None, ) -> WebAssistantsFactory:
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler))
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            BitstampRESTPreProcessor(),
            TimeSynchronizerRESTPreProcessor(synchronizer=time_synchronizer, time_provider=time_provider),
        ],
    )
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None,
        domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=public_rest_url(path_url=CONSTANTS.STATUS_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.STATUS_URL,
    )
    server_time = response["server_time"]
    return server_time
