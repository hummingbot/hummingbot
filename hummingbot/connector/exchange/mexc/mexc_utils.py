#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import time
from decimal import Decimal

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData


def num_to_increment(num):
    return Decimal(10) ** -num


CENTRALIZED = True

EXAMPLE_PAIR = 'BTC-USDT'

DEFAULT_FEES = [0.2, 0.2]


class MexcConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="mexc", client_data=None)
    mexc_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your MEXC API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    mexc_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your MEXC secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "mexc"


KEYS = MexcConfigMap.construct()

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
