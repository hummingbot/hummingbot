import math
# from typing import Dict, List
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce_low_res
# from . import crypto_com_constants as Constants

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = [0.1, 0.1]

# HBOT_BROKER_ID = "HBOT-"


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "/")

# # deeply merge two dictionaries
# def merge_dicts(source: Dict, destination: Dict) -> Dict:
#     for key, value in source.items():
#         if isinstance(value, dict):
#             # get node or create one
#             node = destination.setdefault(key, {})
#             merge_dicts(value, node)
#         else:
#             destination[key] = value

#     return destination


# # join paths
# def join_paths(*paths: List[str]) -> str:
#     return "/".join(paths)


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return get_tracking_nonce_low_res()


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


KEYS = {
    "bitmax_api_key":
        ConfigVar(key="bitmax_api_key",
                  prompt="Enter your Bitmax API key >>> ",
                  required_if=using_exchange("bitmax"),
                  is_secure=True,
                  is_connect_key=True),
    "bitmax_secret_key":
        ConfigVar(key="bitmax_secret_key",
                  prompt="Enter your Bitmax secret key >>> ",
                  required_if=using_exchange("bitmax"),
                  is_secure=True,
                  is_connect_key=True),
}
