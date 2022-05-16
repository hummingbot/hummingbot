import math
import re
from typing import Dict, List

from pydantic import Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap, ClientFieldData
from hummingbot.connector.exchange.wazirx import wazirx_constants as CONSTANTS
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce, get_tracking_nonce_low_res

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


class WazirxConfigMap(BaseConnectorConfigMap):
    connector: str = Field(default="wazirx", client_data=None)
    wazirx_api_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your WazirX API key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )
    wazirx_secret_key: SecretStr = Field(
        default=...,
        client_data=ClientFieldData(
            prompt=lambda cm: "Enter your WazirX secret key",
            is_secure=True,
            is_connect_key=True,
            prompt_on_new=True,
        )
    )

    class Config:
        title = "wazirx"


KEYS = WazirxConfigMap.construct()
