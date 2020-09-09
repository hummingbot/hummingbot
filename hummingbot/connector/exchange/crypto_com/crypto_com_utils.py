import math
from typing import Dict, List

from hummingbot.core.utils.tracking_nonce import get_tracking_nonce, get_tracking_nonce_low_res
from . import crypto_com_constants as Constants


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
    side = "buy" if is_buy else "sell"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


def get_api_reason(code: str) -> str:
    return Constants.API_REASONS.get(int(code), code)
