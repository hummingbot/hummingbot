#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import time


def seconds():
    return int(time.time())


def milliseconds():
    return int(time.time() * 1000)


def microseconds():
    return int(time.time() * 1000000)


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("_", "-");


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "_");

