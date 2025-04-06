import time
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

import hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest
from hummingbot.core.web_assistant.rest_pre_processors import RESTPreProcessorBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class HyperliquidPerpetualRESTPreProcessor(RESTPreProcessorBase):

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


def rest_url(path_url: str, domain: str = "hyperliquid_perpetual"):
    base_url = CONSTANTS.PERPETUAL_BASE_URL if domain == "hyperliquid_perpetual" else CONSTANTS.TESTNET_BASE_URL
    return base_url + path_url


def wss_url(domain: str = "hyperliquid_perpetual"):
    base_ws_url = CONSTANTS.PERPETUAL_WS_URL if domain == "hyperliquid_perpetual" else CONSTANTS.TESTNET_WS_URL
    return base_ws_url


def build_api_factory(
        throttler: Optional[AsyncThrottler] = None,
        auth: Optional[AuthBase] = None) -> WebAssistantsFactory:
    throttler = throttler or create_throttler()
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[HyperliquidPerpetualRESTPreProcessor()],
        auth=auth)
    return api_factory


def build_api_factory_without_time_synchronizer_pre_processor(throttler: AsyncThrottler) -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory(
        throttler=throttler,
        rest_pre_processors=[HyperliquidPerpetualRESTPreProcessor()])
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


def order_type_to_tuple(order_type) -> Tuple[int, float]:
    if "limit" in order_type:
        tif = order_type["limit"]["tif"]
        if tif == "Gtc":
            return 2, 0
        elif tif == "Alo":
            return 1, 0
        elif tif == "Ioc":
            return 3, 0
    elif "trigger" in order_type:
        trigger = order_type["trigger"]
        trigger_px = trigger["triggerPx"]
        if trigger["isMarket"] and trigger["tpsl"] == "tp":
            return 4, trigger_px
        elif not trigger["isMarket"] and trigger["tpsl"] == "tp":
            return 5, trigger_px
        elif trigger["isMarket"] and trigger["tpsl"] == "sl":
            return 6, trigger_px
        elif not trigger["isMarket"] and trigger["tpsl"] == "sl":
            return 7, trigger_px
    raise ValueError("Invalid order type", order_type)


def float_to_int_for_hashing(x: float) -> int:
    return float_to_int(x, 8)


def float_to_int(x: float, power: int) -> int:
    with_decimals = x * 10 ** power
    if abs(round(with_decimals) - with_decimals) >= 1e-3:
        raise ValueError("float_to_int causes rounding", x)
    return round(with_decimals)


def str_to_bytes16(x: str) -> bytearray:
    assert x.startswith("0x")
    return bytearray.fromhex(x[2:])


def order_grouping_to_number(grouping) -> int:
    if grouping == "na":
        return 0
    elif grouping == "normalTpsl":
        return 1
    elif grouping == "positionTpsl":
        return 2


def order_spec_to_order_wire(order_spec):
    return {
        "a": order_spec["asset"],
        "b": order_spec["isBuy"],
        "p": float_to_wire(order_spec["limitPx"]),
        "s": float_to_wire(order_spec["sz"]),
        "r": order_spec["reduceOnly"],
        "t": order_type_to_wire(order_spec["orderType"]),
        "c": order_spec["cloid"],
    }


def float_to_wire(x: float) -> str:
    rounded = "{:.8f}".format(x)
    if abs(float(rounded) - x) >= 1e-12:
        raise ValueError("float_to_wire causes rounding", x)
    if rounded == "-0":
        rounded = "0"
    normalized = Decimal(rounded).normalize()
    return f"{normalized:f}"


def order_type_to_wire(order_type):
    if "limit" in order_type:
        return {"limit": order_type["limit"]}
    elif "trigger" in order_type:
        return {
            "trigger": {
                "triggerPx": float_to_wire(order_type["trigger"]["triggerPx"]),
                "tpsl": order_type["trigger"]["tpsl"],
                "isMarket": order_type["trigger"]["isMarket"],
            }
        }
    raise ValueError("Invalid order type", order_type)
