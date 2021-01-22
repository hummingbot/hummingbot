import random
import string
import math
from typing import Tuple
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce_low_res

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True

EXAMPLE_PAIR = "BTC-USDT"

DEFAULT_FEES = [0.1, 0.1]


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("/", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "/")


# get timestamp in milliseconds
def get_ms_timestamp() -> int:
    return get_tracking_nonce_low_res()


# convert milliseconds timestamp to seconds
def ms_timestamp_to_s(ms: int) -> int:
    return math.floor(ms / 1e3)


def uuid32():
    return ''.join(random.choice(string.ascii_uppercase + string.ascii_lowercase + string.digits) for _ in range(32))


def derive_order_id(user_uid: str, cl_order_id: str, ts: int, order_src='a') -> str:
    """
    Server order generator based on user info and input.
    :param user_uid: user uid
    :param cl_order_id: user random digital and number id
    :param ts: order timestamp in milliseconds
    :param order_src: 'a' for rest api order, 's' for websocket order.
    :return: order id of length 32
    """
    return (order_src + format(ts, 'x')[-11:] + user_uid[-11:] + cl_order_id[-9:])[:32]


def gen_order_id(userUid: str) -> Tuple[str, int]:
    """
    Generate an order id
    :param user_uid: user uid
    :return: order id of length 32
    """
    time = get_ms_timestamp()
    return [
        derive_order_id(
            userUid,
            uuid32(),
            time
        ),
        time
    ]


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
