from typing import Callable, Optional

from hummingbot.connector.derivative.deepcoin_perpetual import deepcoin_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class HeadersContentRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json" if request.method == RESTMethod.POST else "application/x-www-form-urlencoded"
        )
        return request


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
            HeadersContentRESTPreProcessor(),
        ],
    )
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: Optional[AsyncThrottler] = None, domain: str = CONSTANTS.DEFAULT_DOMAIN
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    url = public_rest_url(endpoint=CONSTANTS.SERVER_TIME_PATH_URL, domain=domain)
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
        method=RESTMethod.GET,
    )
    time_data = response.get("data")
    if time_data is not None:
        server_time = float(time_data["ts"])
        return server_time
    else:
        raise ValueError("Failed to get server time")


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(throttler=throttler)
    return api_factory


def public_rest_url(endpoint: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Get public REST URL for endpoint
    """
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.REST_URLS.get(variant) + endpoint


def public_wss_url(domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """
    Get public WebSocket URL
    """
    variant = domain if domain else CONSTANTS.DEFAULT_DOMAIN
    return CONSTANTS.WSS_PUBLIC_URLS.get(variant)
