import time
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class EvedexPerpetualRESTPreProcessor(RESTPreProcessorBase):
    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN) -> str:
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = CONSTANTS.DOMAIN) -> str:
    return CONSTANTS.PERPETUAL_WS_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_WS_URL


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[EvedexPerpetualRESTPreProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[EvedexPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler, domain) -> float:
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    return rule.get("status", "").upper() == "ACTIVE"
