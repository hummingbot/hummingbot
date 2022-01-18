import math
import zlib
from typing import Dict, List, Tuple

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.data_type.order_book_message import OrderBookMessage
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce, get_tracking_nonce_low_res
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.25, 0.25]

HBOT_BROKER_ID = "hummingbot-"


# deeply merge two dictionaries
def merge_dicts(source: Dict, destination: Dict) -> Dict:
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dicts(value, node)
        else:
            destination[key] = value

    return destination


# join paths
def join_paths(*paths: List[str]) -> str:
    return "/".join(paths)


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return get_tracking_nonce_low_res()


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


def convert_snapshot_message_to_order_book_row(message: OrderBookMessage) -> Tuple[List[OrderBookRow], List[OrderBookRow]]:
    update_id = message.update_id
    data = message.content
    bids, asks = [], []

    if "buys" in data:
        bids = [
            OrderBookRow(float(bid["price"]), float(bid["amount"]), update_id) for bid in data["buys"]
        ]
    elif "bids" in data:
        bids = [
            OrderBookRow(float(bid[0]), float(bid[1]), update_id) for bid in data["bids"]
        ]
    sorted(bids, key=lambda a: a.price)

    if "sells" in data:
        asks = [
            OrderBookRow(float(ask["price"]), float(ask["amount"]), update_id) for ask in data["sells"]
        ]
    elif "asks" in data:
        asks = [
            OrderBookRow(float(ask[0]), float(ask[1]), update_id) for ask in data["asks"]
        ]
    sorted(asks, key=lambda a: a.price)

    return bids, asks


def convert_diff_message_to_order_book_row(message: OrderBookMessage) -> Tuple[List[OrderBookRow], List[OrderBookRow]]:
    update_id = message.update_id
    data = message.content
    bids, asks = [], []

    if "buys" in data:
        bids = [
            OrderBookRow(float(bid["price"]), float(bid["amount"]), update_id) for bid in data["buys"]
        ]
    elif "bids" in data:
        bids = [
            OrderBookRow(float(bid[0]), float(bid[1]), update_id) for bid in data["bids"]
        ]
    sorted(bids, key=lambda a: a.price)

    if "sells" in data:
        asks = [
            OrderBookRow(float(ask["price"]), float(ask["amount"]), update_id) for ask in data["sells"]
        ]
    elif "asks" in data:
        asks = [
            OrderBookRow(float(ask[0]), float(ask[1]), update_id) for ask in data["asks"]
        ]
    sorted(asks, key=lambda a: a.price)

    return bids, asks


# Request ID class
class RequestId:
    """
    Generate request ids
    """
    _request_id: int = 0

    @classmethod
    def generate_request_id(cls) -> int:
        return get_tracking_nonce()


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("_", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "_")


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{HBOT_BROKER_ID}{side}-{trading_pair}-{get_tracking_nonce()}"


# Decompress WebSocket messages
def decompress_ws_message(message):
    if type(message) == bytes:
        decompress = zlib.decompressobj(-zlib.MAX_WBITS)
        inflated = decompress.decompress(message)
        inflated += decompress.flush()
        return inflated.decode('UTF-8')
    else:
        return message


def compress_ws_message(message):
    if type(message) == str:
        message = message.encode()
        compress = zlib.compressobj(wbits=-zlib.MAX_WBITS)
        deflated = compress.compress(message)
        deflated += compress.flush()
        return deflated
    else:
        return message


KEYS = {
    "bitmart_api_key":
        ConfigVar(key="bitmart_api_key",
                  prompt="Enter your BitMart API key >>> ",
                  required_if=using_exchange("bitmart"),
                  is_secure=True,
                  is_connect_key=True),
    "bitmart_secret_key":
        ConfigVar(key="bitmart_secret_key",
                  prompt="Enter your BitMart secret key >>> ",
                  required_if=using_exchange("bitmart"),
                  is_secure=True,
                  is_connect_key=True),
    "bitmart_memo":
        ConfigVar(key="bitmart_memo",
                  prompt="Enter your BitMart API Memo >>> ",
                  required_if=using_exchange("bitmart"),
                  is_secure=True,
                  is_connect_key=True),
}


def build_api_factory() -> WebAssistantsFactory:
    api_factory = WebAssistantsFactory()
    return api_factory
