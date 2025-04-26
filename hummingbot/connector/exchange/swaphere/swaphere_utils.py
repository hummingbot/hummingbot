import re
from datetime import datetime
from typing import Optional, Tuple

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce

TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(BTC|ETH|USD|USDT|BNB|DAI|XRP|BCH|LTC|EOS|XLM|LINK|DOT|DOGE)$")


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    """
    Splits a trading pair into base and quote assets
    Example: BTCUSDT -> (BTC, USDT)
    """
    m = TRADING_PAIR_SPLITTER.match(trading_pair)
    if m is None:
        raise ValueError(f"Could not parse trading pair {trading_pair}")
    return m.group(1), m.group(2)


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> str:
    """
    Convert from exchange format (like BTC-USDT) to client format (like BTC-USDT)
    """
    return exchange_trading_pair  # If already in expected format


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    """
    Convert from client format (like BTC-USDT) to exchange format
    """
    return hb_trading_pair  # If already in expected format


def get_new_client_order_id(is_buy: bool, trading_pair: str) -> str:
    """
    Creates a client order id for a new order
    """
    side = "B" if is_buy else "S"
    return f"{side}-{trading_pair}-{get_tracking_nonce()}"


KEYS = {
    "swaphere_api_key": ConfigVar(
        key="swaphere_api_key",
        prompt="Enter your Swaphere API key >>> ",
        required_if=using_exchange("swaphere"),
        is_secure=True,
        is_connect_key=True,
    ),
    "swaphere_secret_key": ConfigVar(
        key="swaphere_secret_key",
        prompt="Enter your Swaphere secret key >>> ",
        required_if=using_exchange("swaphere"),
        is_secure=True,
        is_connect_key=True,
    ),
    "swaphere_passphrase": ConfigVar(
        key="swaphere_passphrase",
        prompt="Enter your Swaphere passphrase (leave empty if not required) >>> ",
        required_if=using_exchange("swaphere"),
        is_secure=True,
        is_connect_key=True,
    ),
} 