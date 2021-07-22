#!/usr/bin/env python

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-CAD"

# NDAX fees: https://ndax.io/fees
DEFAULT_FEES = [0.2, 0.2]


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")
