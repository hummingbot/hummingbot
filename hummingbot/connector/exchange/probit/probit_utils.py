#!/usr/bin/env python

import dateutil.parser as dp

from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Tuple
)

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.data_type.order_book_message import OrderBookMessage

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.2, 0.2]


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


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


KEYS = {
    "probit_api_key":
        ConfigVar(key="probit_api_key",
                  prompt="Enter your ProBit Client ID >>> ",
                  required_if=using_exchange("probit"),
                  is_secure=True,
                  is_connect_key=True),
    "probit_secret_key":
        ConfigVar(key="probit_secret_key",
                  prompt="Enter your ProBit secret key >>> ",
                  required_if=using_exchange("probit"),
                  is_secure=True,
                  is_connect_key=True),
}

OTHER_DOMAINS = ["probit_kr"]
OTHER_DOMAINS_PARAMETER = {"probit_kr": "kr"}
OTHER_DOMAINS_EXAMPLE_PAIR = {"probit_kr": "BTC-USDT"}
OTHER_DOMAINS_DEFAULT_FEES = {"probit_kr": [0.2, 0.2]}
OTHER_DOMAINS_KEYS = {
    "probit_kr": {
        "probit_kr_api_key":
            ConfigVar(key="probit_kr_api_key",
                      prompt="Enter your ProBit KR Client ID >>> ",
                      required_if=using_exchange("probit_kr"),
                      is_secure=True,
                      is_connect_key=True),
        "probit_kr_secret_key":
            ConfigVar(key="probit_kr_secret_key",
                      prompt="Enter your ProBit KR secret key >>> ",
                      required_if=using_exchange("probit_kr"),
                      is_secure=True,
                      is_connect_key=True),
    }
}
