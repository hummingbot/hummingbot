import math
from typing import List

from dateutil.parser import parse as dateparse

from hummingbot.client.config.config_methods import using_exchange
from hummingbot.client.config.config_var import ConfigVar
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce, get_tracking_nonce_low_res

from . import btc_markets_constants as CONSTANTS

CENTRALIZED = True

EXAMPLE_PAIR = "XRP-AUD"

# Using AUD Market Pair rates, but need to figure out how to determine 30 day AUD vol for rolling
# https://www.btcmarkets.net/fees
DEFAULT_FEES = [0.85, 0.85]

HBOT_BROKER_ID = "HBOT-"


# join paths
def join_paths(*paths: List[str]) -> str:
    return "/".join(paths)


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return get_tracking_nonce_low_res()


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


# convert date string to timestamp
def str_date_to_ts(date: str) -> int:
    return int(dateparse(date).timestamp())


def get_rest_url(path_url: str, api_version: str = CONSTANTS.REST_API_VERSION) -> str:
    return f"{CONSTANTS.REST_URL}{api_version}{path_url}"


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


def get_api_reason(code: str) -> str:
    return CONSTANTS.API_REASONS.get(int(code), code)


KEYS = {
    "btc_markets_api_key":
        ConfigVar(key="btc_markets_api_key",
                  prompt="Enter your BTCMarkets API key >>> ",
                  required_if=using_exchange("btc_markets"),
                  is_secure=True,
                  is_connect_key=True),
    "btc_markets_secret_key":
        ConfigVar(key="btc_markets_secret_key",
                  prompt="Enter your BTCMarkets secret key >>> ",
                  required_if=using_exchange("btc_markets"),
                  is_secure=True,
                  is_connect_key=True),
}
