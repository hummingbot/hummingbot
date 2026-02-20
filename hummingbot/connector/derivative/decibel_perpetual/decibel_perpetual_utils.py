from decimal import Decimal
from typing import Optional

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import EXCHANGE_NAME


def convert_from_exchange_symbol(exchange_symbol: str) -> str:
    """
    Converts Decibel symbol format to Hummingbot symbol format
    Example: "BTC-PERP" -> "BTC-USDT"
    """
    if "-PERP" in exchange_symbol:
        return exchange_symbol.replace("-PERP", "-USD")
    return exchange_symbol


def convert_to_exchange_symbol(trading_pair: str) -> str:
    """
    Converts Hummingbot symbol format to Decibel symbol format
    Example: "BTC-USDT" -> "BTC-PERP"
    """
    if "-USD" in trading_pair:
        return trading_pair.replace("-USD", "-PERP")
    return trading_pair


def get_pair_prefix(trading_pair: str) -> str:
    """Returns the base asset from a trading pair"""
    return trading_pair.split("-")[0]


def get_pair_suffix(trading_pair: str) -> str:
    """Returns the quote asset from a trading pair"""
    return trading_pair.split("-")[1]


def_exchange_trading_pair = "BTC-USD"


def get_exchange_trading_pair(trading_pair: str) -> str:
    """Returns the exchange trading pair for an order"""
    return convert_to_exchange_symbol(trading_pair)


def get_original_trading_pair(exchange_symbol: str) -> str:
    """Returns the original trading pair from an exchange symbol"""
    return convert_from_exchange_symbol(exchange_symbol)
