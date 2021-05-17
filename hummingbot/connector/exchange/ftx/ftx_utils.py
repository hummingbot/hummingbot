from typing import (
    Optional,
    Tuple)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True


EXAMPLE_PAIR = "BTC-USD"


DEFAULT_FEES = [0.02, 0.07]


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = trading_pair.split("/")
        return m[0], m[1]
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
    return hb_trading_pair.replace("-", "/")


KEYS = {
    "ftx_api_key":
        ConfigVar(key="ftx_api_key",
                  prompt="Enter your FTX API key >>> ",
                  required_if=using_exchange("ftx"),
                  is_secure=True,
                  is_connect_key=True),
    "ftx_secret_key":
        ConfigVar(key="ftx_secret_key",
                  prompt="Enter your FTX API secret >>> ",
                  required_if=using_exchange("ftx"),
                  is_secure=True,
                  is_connect_key=True),
    "ftx_subaccount_name":
        ConfigVar(key="ftx_subaccount_name",
                  prompt="Enter your FTX subaccount name (if this is not a subaccount, leave blank) >>> ",
                  required_if=using_exchange("ftx"),
                  is_secure=True,
                  is_connect_key=True),
}
