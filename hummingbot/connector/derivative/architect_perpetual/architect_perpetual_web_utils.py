from typing import Callable, Optional

import pandas as pd

from hummingbot.connector.derivative.architect_perpetual import architect_perpetual_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def public_rest_url(path_url: str, domain: str) -> str:
    return f"{CONSTANTS.REST_URL_BASES[domain]}{path_url}"


def private_rest_url(path_url: str, domain: str) -> str:
    return f"{CONSTANTS.REST_URL_BASES[domain]}{path_url}"


def public_ws_url(domain: str) -> str:
    return CONSTANTS.PUBLIC_WS_URL[domain]


def private_ws_url(domain: str) -> str:
    return CONSTANTS.PRIVATE_WS_URL[domain]


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    time_provider: Optional[Callable] = None,
    auth: Optional[AuthBase] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (lambda: get_current_server_time(throttler=throttler, domain=domain))
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
    throttler: Optional[AsyncThrottler] = None
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(throttler=throttler)

    return api_factory


def create_throttler() -> AsyncThrottler:
    throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

    return throttler


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None, domain: str = CONSTANTS.DEFAULT_DOMAIN
) -> float:
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()

    url = public_rest_url(path_url=CONSTANTS.SERVER_TIME_ENDPOINT, domain=domain)
    response = await rest_assistant.execute_request(
        url=url,
        throttler_limit_id=CONSTANTS.SERVER_TIME_ENDPOINT,
        method=RESTMethod.GET,
        return_err=True,
    )
    timestamp = pd.Timestamp(response["timestamp"]).timestamp()

    return timestamp
