#!/usr/bin/env python

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import dateutil.parser as dp
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

DEFAULT_FEES = TradeFeeSchema(
    maker_percent_fee_decimal=Decimal("0.002"),
    taker_percent_fee_decimal=Decimal("0.002"),
)


CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"


def convert_iso_to_epoch(ts: str) -> float:
    return dp.parse(ts).timestamp()


def get_iso_time_now() -> str:
    return datetime.utcnow().isoformat()[:-3] + 'Z'


def convert_snapshot_message_to_order_book_row(message: OrderBookMessage) -> Tuple[List[OrderBookRow], List[OrderBookRow]]:
    update_id = message.update_id
    data = []
    if "data" in message.content:  # From REST API
        data: List[Dict[str, Any]] = message.content["data"]
    elif "order_books" in message.content:  # From Websocket API
        data: List[Dict[str, Any]] = message.content["order_books"]
    bids, asks = [], []

    for entry in data:
        order_row = OrderBookRow(float(entry["price"]), float(entry["quantity"]), update_id)
        if entry["side"] == "buy":
            bids.append(order_row)
        else:  # entry["type"] == "Sell":
            asks.append(order_row)

    return bids, asks


def convert_diff_message_to_order_book_row(message: OrderBookMessage) -> Tuple[List[OrderBookRow], List[OrderBookRow]]:
    update_id = message.update_id
    data = message.content["order_books"]
    bids = []
    asks = []

    for entry in data:
        order_row = OrderBookRow(float(entry["price"]), float(entry["quantity"]), update_id)
        if entry["side"] == "buy":
            bids.append(order_row)
        elif entry["side"] == "sell":
            asks.append(order_row)

    return bids, asks


class ProbitConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="probit", client_data=None)
    probit_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your ProBit Client ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    probit_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your ProBit secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "probit"


KEYS = ProbitConfigMap.construct()

OTHER_DOMAINS = ["probit_kr"]
OTHER_DOMAINS_PARAMETER = {"probit_kr": "kr"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"probit_kr": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"probit_kr": [0.2, 0.2]}


class ProbitKrConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="probit_kr", client_data=None)
    probit_kr_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your ProBit KR Client ID",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    probit_kr_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your ProBit KR secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "probit_kr"


OTHER_DOMAINS_KEYS = {"probit_kr": ProbitKrConfigMap.construct()}
