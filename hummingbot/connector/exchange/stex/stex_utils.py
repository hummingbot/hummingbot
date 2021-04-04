import re
from typing import (
    Optional,
    Tuple)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True

EXAMPLE_PAIR = "ZRX-ETH"

DEFAULT_FEES = [0.2, 0.2]

def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    return exchange_trading_pair.replace("_", "-")


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.replace("-", "_")

KEYS = {
    "stex_access_token":
        ConfigVar(key="stex_access_token",
                  prompt="Enter your Stex access token >>> ",
                  required_if=using_exchange("stex"),
                  is_secure=True,
                  is_connect_key=True),
}
