import hummingbot.connector.exchange.kraken.kraken_constants as constants
from typing import (
    Optional,
    Tuple)

from hummingbot.client.config.config_var import ConfigVar
from hummingbot.client.config.config_methods import using_exchange


CENTRALIZED = True

EXAMPLE_PAIR = "ETH-USDC"

DEFAULT_FEES = [0.16, 0.26]


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    return tuple(convert_from_exchange_trading_pair(trading_pair).split("-"))


def convert_from_exchange_symbol(symbol: str) -> str:
    # Assuming if starts with Z or X and has 4 letters then Z/X is removable
    if (symbol[0] == "X" or symbol[0] == "Z") and len(symbol) == 4:
        symbol = symbol[1:]
    return constants.KRAKEN_TO_HB_MAP.get(symbol, symbol)


def convert_to_exchange_symbol(symbol: str) -> str:
    inverted_kraken_to_hb_map = {v: k for k, v in constants.KRAKEN_TO_HB_MAP.items()}
    return inverted_kraken_to_hb_map.get(symbol, symbol)


def split_to_base_quote(exchange_trading_pair: str) -> (Optional[str], Optional[str]):
    base, quote = exchange_trading_pair.split("-")
    return base, quote


def convert_from_exchange_trading_pair(exchange_trading_pair: str, available_trading_pairs: Optional[Tuple] = None) -> Optional[str]:
    base, quote = "", ""
    if "-" in exchange_trading_pair:
        base, quote = split_to_base_quote(exchange_trading_pair)
    elif "/" in exchange_trading_pair:
        base, quote = exchange_trading_pair.split("/")
    elif len(available_trading_pairs) > 0:
        # If trading pair has no spaces (i.e. ETHUSDT). Then it will have to match with the existing pairs
        # Option 1: Using traditional naming convention
        connector_trading_pair = {''.join(convert_from_exchange_trading_pair(tp).split('-')): tp for tp in available_trading_pairs}.get(
            exchange_trading_pair)
        if not connector_trading_pair:
            # Option 2: Using kraken naming convention ( XXBT for Bitcoin, XXDG for Doge, ZUSD for USD, etc)
            connector_trading_pair = {''.join(tp.split('-')): tp for tp in available_trading_pairs}.get(
                exchange_trading_pair)
        return connector_trading_pair

    if not base or not quote:
        return None
    base = convert_from_exchange_symbol(base)
    quote = convert_from_exchange_symbol(quote)
    return f"{base}-{quote}"


def convert_to_exchange_trading_pair(hb_trading_pair: str, delimiter: str = "") -> str:
    """
    Note: The result of this method can safely be used to submit/make queries.
    Result shouldn't be used to parse responses as Kraken add special formating to most pairs.
    """
    if "-" in hb_trading_pair:
        base, quote = hb_trading_pair.split("-")
    elif "/" in hb_trading_pair:
        base, quote = hb_trading_pair.split("/")
    else:
        return hb_trading_pair
    base = convert_to_exchange_symbol(base)
    quote = convert_to_exchange_symbol(quote)

    exchange_trading_pair = f"{base}{delimiter}{quote}"
    return exchange_trading_pair


KEYS = {
    "kraken_api_key":
        ConfigVar(key="kraken_api_key",
                  prompt="Enter your Kraken API key >>> ",
                  required_if=using_exchange("kraken"),
                  is_secure=True,
                  is_connect_key=True),
    "kraken_secret_key":
        ConfigVar(key="kraken_secret_key",
                  prompt="Enter your Kraken secret key >>> ",
                  required_if=using_exchange("kraken"),
                  is_secure=True,
                  is_connect_key=True),
}
