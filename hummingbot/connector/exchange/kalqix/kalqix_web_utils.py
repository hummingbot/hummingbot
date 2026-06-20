from typing import Callable, Optional

import hummingbot.connector.exchange.kalqix.kalqix_constants as CONSTANTS
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.connector.utils import TimeSynchronizerRESTPreProcessor
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


def rest_url(path_url: str, domain: str = CONSTANTS.DEFAULT_DOMAIN) -> str:
    """KalqiX has one base URL for both public and private endpoints; the
    public-vs-private split lives in middleware, not URL shape."""
    return CONSTANTS.rest_url(domain) + path_url


# Hummingbot's `exchange_py_base` calls `web_utils.public_rest_url` and
# `web_utils.private_rest_url` explicitly. Both map to the same base URL on
# KalqiX since auth lives in headers, not URL shape.
public_rest_url = rest_url
private_rest_url = rest_url


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    time_synchronizer: Optional[TimeSynchronizer] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
    time_provider: Optional[Callable] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    time_synchronizer = time_synchronizer or TimeSynchronizer()
    time_provider = time_provider or (
        lambda: get_current_server_time(throttler=throttler, domain=domain)
    )
    return WebAssistantsFactory(
        throttler=throttler,
        auth=auth,
        rest_pre_processors=[
            TimeSynchronizerRESTPreProcessor(
                synchronizer=time_synchronizer, time_provider=time_provider
            ),
        ],
    )


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(throttler=throttler)


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
    throttler: Optional[AsyncThrottler] = None,
    domain: str = CONSTANTS.DEFAULT_DOMAIN,
) -> float:
    """Calls `GET /v1/time` and returns the `server_time` field (ms).

    Note: KalqiX's response uses `server_time` (snake_case), not the
    `serverTime` spelling some other exchanges use.
    """
    throttler = throttler or create_throttler()
    api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
    rest_assistant = await api_factory.get_rest_assistant()
    response = await rest_assistant.execute_request(
        url=rest_url(CONSTANTS.SERVER_TIME_PATH_URL, domain=domain),
        method=RESTMethod.GET,
        throttler_limit_id=CONSTANTS.SERVER_TIME_PATH_URL,
    )
    return response["server_time"]
