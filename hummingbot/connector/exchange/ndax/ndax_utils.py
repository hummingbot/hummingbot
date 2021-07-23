#!/usr/bin/env python

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


CENTRALIZED = True

EXAMPLE_PAIR = "BTC-CAD"

# NDAX fees: https://ndax.io/fees
DEFAULT_FEES = [0.2, 0.2]

HBOT_ORDER_ID_PREFIX = "HBOT"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{HBOT_ORDER_ID_PREFIX}-{side}-{trading_pair}-{get_tracking_nonce()}"
