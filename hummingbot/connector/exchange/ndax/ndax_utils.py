#!/usr/bin/env python

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-CAD"

# NDAX fees: https://ndax.io/fees
# Fees have to be expressed as percent value
DEFAULT_FEES = [2, 2]


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "")
