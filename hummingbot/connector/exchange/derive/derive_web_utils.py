import time

# from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import hummingbot.connector.exchange.derive.derive_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, RESTResponse
from hummingbot.core.web_assistant.rest_post_processors import RESTPostProcessorBase
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

MAX_INT_256 = 2**255 - 1
MIN_INT_256 = -(2**255)
MAX_INT_32 = 2**31 - 1


class DeriveRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = (
            "application/json"
        )
        return request


class DeriveRESTPostProcessor(RESTPostProcessorBase):

    async def post_process(self, request: RESTResponse) -> RESTResponse:
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = "derive"):
    base_url = CONSTANTS.BASE_URL if domain == "derive" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = "derive"):
    base_ws_url = CONSTANTS.WSS_URL if domain == "derive" else CONSTANTS.TESTNET_WSS_URL
    return base_ws_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DeriveRESTPreProcessor()],
        rest_post_processors=[DeriveRESTPostProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DeriveRESTPreProcessor()],
        rest_post_processors=[DeriveRESTPostProcessor()]),
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
    return True


def utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def order_to_call(order):
    return {
        "instrument_name": order["instrument_name"],
        "direction": order["direction"],
        "order_type": order["order_type"],
        "mmp": False,
        "time_in_force": order["time_in_force"],
        "label": order["label"]
    }
