import re
import math
from typing import Dict, List
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce, get_tracking_nonce_low_res
from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(btc|usdt|inr|wrx)$")

CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDT"

DEFAULT_FEES = [0.2, 0.2]

HBOT_BROKER_ID = "HBOT-"


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


def get_min_order_value(trading_pair):
    temp = trading_pair.split("-")
    quote_asset = temp[1]

    if(quote_asset == "INR"):
        mov = "50"
    elif(quote_asset == "USDT"):
        mov = "2"
    elif(quote_asset == "WRX"):
        mov = "1"
    elif(quote_asset == "BTC"):
        mov = "0.0001"
    else:
        mov = "0"

    return mov


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
    temp = TRADING_PAIR_SPLITTER.search(exchange_trading_pair)
    base_asset = temp.group(1)
    quote_asset = temp.group(2)
    return base_asset.upper() + "-" + quote_asset.upper()


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "").lower()


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    side = "B" if is_buy else "S"
    return f"{HBOT_BROKER_ID}{side}-{trading_pair}-{get_tracking_nonce()}"


def get_api_reason(code: str) -> str:
    return CONSTANTS.API_REASONS.get(int(code), code)


KEYS = {
    "wazirx_api_key":
        ConfigVar(key="wazirx_api_key",
                  prompt="Enter your WazirX API key >>> ",
                  required_if=using_exchange("wazirx"),
                  is_secure=True,
                  is_connect_key=True),
    "wazirx_secret_key":
        ConfigVar(key="wazirx_secret_key",
                  prompt="Enter your WazirX secret key >>> ",
                  required_if=using_exchange("wazirx"),
                  is_secure=True,
                  is_connect_key=True),
}
