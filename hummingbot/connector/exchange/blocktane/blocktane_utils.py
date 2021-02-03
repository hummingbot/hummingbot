import re

from typing import Optional, Tuple

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange

CENTRALIZED = True

EXAMPLE_PAIR = "BTC-BRL"

DEFAULT_FEES = [0.35, 0.45]  # The actual fees

KEYS = {
    "blocktane_api_key":
        ConfigVar(key="blocktane_api_key",
                  prompt="Enter your Blocktane API key >>> ",
                  required_if=using_exchange("blocktane"),
                  is_secure=True,
                  is_connect_key=True),
    "blocktane_api_secret":
        ConfigVar(key="blocktane_api_secret",
                  prompt="Enter your Blocktane API secret >>> ",
                  required_if=using_exchange("blocktane"),
                  is_secure=True,
                  is_connect_key=True)
}

TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(BTC|btc|ETH|eth|BRL|brl|PAX|pax)$")


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        if ('/' in trading_pair):
            m = trading_pair.split('/')
            return m[0], m[1]
        else:
            m = TRADING_PAIR_SPLITTER.match(trading_pair)
            return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Blocktane does not split BASEQUOTE (fthusd)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset}-{quote_asset}".upper()


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    return hb_trading_pair.lower().replace("-", "")
