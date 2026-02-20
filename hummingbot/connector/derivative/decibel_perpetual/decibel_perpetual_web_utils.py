import time
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class DecibelPerpetualRESTPreProcessor(RESTPreProcessorBase):

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = CONSTANTS.DOMAIN):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = CONSTANTS.DOMAIN):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == CONSTANTS.DOMAIN else CONSTANTS.TESTNET_WS_URL
    return base_ws_url


def aptos_node_url(domain: str = CONSTANTS.DOMAIN):
    return CONSTANTS.APTOS_MAINNET_NODE if domain == CONSTANTS.DOMAIN else CONSTANTS.APTOS_TESTNET_NODE


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DecibelPerpetualRESTPreProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[DecibelPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(throttler, domain) -> float:
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information.
    """
    return True


def price_to_int(price: float) -> int:
    """Convert a price to Decibel's 9-decimal integer format."""
    return int(round(price * CONSTANTS.DECIMAL_MULTIPLIER))


def size_to_int(size: float) -> int:
    """Convert a size to Decibel's 9-decimal integer format."""
    return int(round(size * CONSTANTS.DECIMAL_MULTIPLIER))


def int_to_price(value: int) -> float:
    """Convert Decibel's 9-decimal integer format back to a float price."""
    return value / CONSTANTS.DECIMAL_MULTIPLIER


def int_to_size(value: int) -> float:
    """Convert Decibel's 9-decimal integer format back to a float size."""
    return value / CONSTANTS.DECIMAL_MULTIPLIER
