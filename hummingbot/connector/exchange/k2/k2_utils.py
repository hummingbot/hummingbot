from typing import Any, Dict, List, Tuple

import dateutil.parser
from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USD"

DEFAULT_FEES = [0.1, 0.1]


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "/")


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


def convert_snapshot_message_to_order_book_row(message: OrderBookMessage) -> Tuple[List[OrderBookRow], List[OrderBookRow]]:
    update_id = message.update_id
    data = message.content["data"]
    bids, asks = [], []

    for entry in data:
        order_row = OrderBookRow(entry["price"], entry["quantity"], update_id)
        if entry["type"] == "Buy":
            bids.append(order_row)
        else:  # entry["type"] == "Sell":
            asks.append(order_row)

    return bids, asks


def convert_diff_message_to_order_book_row(message: OrderBookMessage) -> Tuple[List[OrderBookRow], List[OrderBookRow]]:
    update_id = message.update_id
    data = message.content["data"]
    bids = []
    asks = []

    bid_entries: Dict[str, Any] = data[0]
    ask_entries: Dict[str, Any] = data[1]

    for key, orders in bid_entries.items():
        if key == "side":
            continue
        elif key == "remove":
            for price in orders:
                order_row = OrderBookRow(price, float(0), update_id)
                bids.append(order_row)
        else:  # key == "update" or key == "add":
            for order in orders:
                order_row = OrderBookRow(order["p"], order["q"], update_id)
                bids.append(order_row)

    for key, orders in ask_entries.items():
        if key == "side":
            continue
        elif key == "remove":
            for price in orders:
                order_row = OrderBookRow(price, float(0), update_id)
                asks.append(order_row)
        else:  # key == "update" or key == "add":
            for order in orders:
                order_row = OrderBookRow(order["p"], order["q"], update_id)
                asks.append(order_row)

    return bids, asks


def convert_to_epoch_timestamp(timestamp: str) -> int:
    return int(dateutil.parser.parse(timestamp).timestamp() * 1e3)


class K2ConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="k2", client_data=None)
    k2_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your K2 API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    k2_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your K2 secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "k2"


KEYS = K2ConfigMap.construct()
