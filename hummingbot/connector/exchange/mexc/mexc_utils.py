#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from decimal import Decimal

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

import time


def num_to_increment(num):
    return Decimal(10) ** -num


CENTRALIZED = True

EXAMPLE_PAIR = 'BTC-USDT'

DEFAULT_FEES = [0.2, 0.2]

KEYS = {
    "mexc_api_key":
        ConfigVar(key="mexc_api_key",
                  prompt="Enter your MEXC API key >>> ",
                  required_if=using_exchange("mexc"),
                  is_secure=True,
                  is_connect_key=True),
    "mexc_secret_key":
        ConfigVar(key="mexc_secret_key",
                  prompt="Enter your MEXC secret key >>> ",
                  required_if=using_exchange("mexc"),
                  is_secure=True,
                  is_connect_key=True),
}

ws_status = {
    1: 'NEW',
    2: 'FILLED',
    3: 'PARTIALLY_FILLED',
    4: 'CANCELED',
    5: 'PARTIALLY_CANCELED'
}


def seconds():
    return int(time.time())


def milliseconds():
    return int(time.time() * 1000)


def microseconds():
    return int(time.time() * 1000000)


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("_", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "_")


def ws_order_status_convert_to_str(ws_order_status: int) -> str:
    return ws_status[ws_order_status]
