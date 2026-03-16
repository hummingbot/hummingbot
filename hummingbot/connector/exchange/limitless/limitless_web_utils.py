import time
from typing import Any, Dict, Optional

import hummingbot.connector.exchange.limitless.limitless_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class LimitlessRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = "limitless") -> str:
    return CONSTANTS.BASE_URL + path_url


def wss_url(domain: str = "limitless") -> str:
    return CONSTANTS.WS_URL


def build_api_factory(
    throttler: Optional[AsyncThrottler] = None,
    auth: Optional[AuthBase] = None,
) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    return WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[LimitlessRESTPreProcessor()],
        auth=auth,
    )


def build_api_factory_without_time_synchronizer_pre_processor(
    throttler: AsyncThrottler,
) -> WebAssistantsFactory:
    return WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[LimitlessRESTPreProcessor()],
    )


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler, domain) -> float:
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    return True
