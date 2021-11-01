#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import math

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


def num_to_increment(num):
    return math.pow(10, -num)


CENTRALIZED = True

EXAMPLE_PAIR = 'BTC_USDT'

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
