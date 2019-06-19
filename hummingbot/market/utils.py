#!/usr/bin/env python

import base64
from typing import Dict
from zero_ex.order_utils import Order as ZeroExOrder


def zrx_order_to_json(order: ZeroExOrder) -> Dict[str, any]:
    retval: Dict[str, any] = {}
    for key, value in order.items():
        if not isinstance(value, bytes):
            retval[key] = value
        else:
            retval[f"__binary__{key}"] = base64.b64encode(value).decode("utf8")
    return retval


def json_to_zrx_order(data: Dict[str, any]) -> ZeroExOrder:
    intermediate: Dict[str, any] = {}
    for key, value in data.items():
        if key.startswith("__binary__"):
            target_key = key.replace("__binary__", "")
            intermediate[target_key] = base64.b64decode(value)
        else:
            intermediate[key] = value
    return ZeroExOrder(intermediate)
