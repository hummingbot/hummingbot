#!/usr/bin/env python

import base64
from collections import namedtuple
from typing import Dict, Optional, Tuple

from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

from zero_ex.order_utils import Order as ZeroExOrder

TradeFillOrderDetails = namedtuple("TradeFillOrderDetails", "market exchange_trade_id symbol")


def zrx_order_to_json(order: Optional[ZeroExOrder]) -> Optional[Dict[str, any]]:
    if order is None:
        return None

    retval: Dict[str, any] = {}
    for key, value in order.items():
        if not isinstance(value, bytes):
            retval[key] = value
        else:
            retval[f"__binary__{key}"] = base64.b64encode(value).decode("utf8")
    return retval


def json_to_zrx_order(data: Optional[Dict[str, any]]) -> Optional[ZeroExOrder]:
    if data is None:
        return None

    intermediate: Dict[str, any] = {}
    for key, value in data.items():
        if key.startswith("__binary__"):
            target_key = key.replace("__binary__", "")
            intermediate[target_key] = base64.b64decode(value)
        else:
            intermediate[key] = value
    return ZeroExOrder(intermediate)


def build_api_factory() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory()
    return api_factory


def split_hb_trading_pair(trading_pair: str) -> Tuple[str, str]:
    base, quote = trading_pair.split("-")
    return base, quote


def combine_to_hb_trading_pair(base: str, quote: str) -> str:
    trading_pair = f"{base}-{quote}"
    return trading_pair
