import time
from decimal import Decimal
from typing import Any, Dict, Optional

import hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class EvedexPerpetualRESTPreProcessor(RESTPreProcessorBase):
    """REST pre-processor for EVEDEX API requests."""

    async def pre_process(self, request: RESTRequest) -> RESTRequest:
        if request.headers is None:
            request.headers = {}
        request.headers["Content-Type"] = "application/json"
        request.headers["Accept"] = "application/json"
        return request


def private_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def public_rest_url(*args, **kwargs) -> str:
    return rest_url(*args, **kwargs)


def rest_url(path_url: str, domain: str = "evedex_perpetual") -> str:
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "evedex_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = "evedex_perpetual") -> str:
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "evedex_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[EvedexPerpetualRESTPreProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(
        throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[EvedexPerpetualRESTPreProcessor()])
    return api_factory


def create_throttler() -> AsyncThrottler:
    return AsyncThrottler(CONSTANTS.RATE_LIMITS)


async def get_current_server_time(
        throttler: AsyncThrottler,
        domain: str
) -> float:
    return time.time()


def is_exchange_information_valid(rule: Dict[str, Any]) -> bool:
    status = rule.get("status", "active")
    return status.lower() in ("active", "trading")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    quote_currencies = ["USDT", "USDC", "USD", "ETH", "BTC"]
    for quote in quote_currencies:
        if exchange_trading_pair.endswith(quote):
            base = exchange_trading_pair[:-len(quote)]
            return f"{base}-{quote}"
    return f"{exchange_trading_pair[:-4]}-{exchange_trading_pair[-4:]}"


def float_to_string(value: float, precision: int = 8) -> str:
    return f"{value:.{precision}f}".rstrip("0").rstrip(".")


def parse_order_side(side: str) -> str:
    return side.lower()


def parse_order_type(order_type: str) -> str:
    return order_type.lower()
