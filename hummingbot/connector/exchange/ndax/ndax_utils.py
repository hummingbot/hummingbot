#!/usr/bin/env python

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce


CENTRALIZED = True

EXAMPLE_PAIR = "BTC-CAD"

# NDAX fees: https://ndax.io/fees
# Fees have to be expressed as percent value
DEFAULT_FEES = [2, 2]


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    ts_micro_sec: int = get_tracking_nonce()
    return f"{int(ts_micro_sec // 1e3)}"
