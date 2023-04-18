import time
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BitComPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json"
        )
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = "bit_com_perpetual"):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "bit_com_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = "bit_com_perpetual"):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "bit_com_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[BitComPerpetualRESTPreProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[BitComPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler,
        domain
) -> float:
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    if rule["category"] == "future" and rule["active"]:
        valid = True
    else:
        valid = False
    return valid
