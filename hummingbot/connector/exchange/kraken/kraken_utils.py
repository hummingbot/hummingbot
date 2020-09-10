import hummingbot.connector.exchange.kraken.kraken_constants as constants
from typing import (
    Optional,
    Tuple)


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    return tuple(convert_from_exchange_trading_pair(trading_pair).split("-"))


def clean_symbol(symbol: str) -> str:
    if len(symbol) == 4 and symbol[0] == "X" or symbol[0] == "Z":
        symbol = symbol[1:]
    if symbol == "XBT":
        symbol = "BTC"
    return symbol


def convert_from_exchange_symbol(symbol: str) -> str:
    if (len(symbol) == 4 or len(symbol) == 6) and (symbol[0] == "X" or symbol[0] == "Z"):
        symbol = symbol[1:]
    if symbol == "XBT":
        symbol = "BTC"
    return symbol


def convert_to_exchange_symbol(symbol: str) -> str:
    if symbol == "BTC":
        symbol = "XBT"
    return symbol


def split_to_base_quote(exchange_trading_pair: str) -> (Optional[str], Optional[str]):
    base, quote = None, None
    for quote_asset in constants.QUOTES:
        if quote_asset == exchange_trading_pair[-len(quote_asset):]:
            if len(exchange_trading_pair[:-len(quote_asset)]) > 2 or exchange_trading_pair[:-len(quote_asset)] == "SC":
                base, quote = exchange_trading_pair[:-len(quote_asset)], exchange_trading_pair[-len(quote_asset):]
                break
    if not base:
        quote_asset_d = [quote + ".d" for quote in constants.QUOTES]
        for quote_asset in quote_asset_d:
            if quote_asset == exchange_trading_pair[-len(quote_asset):]:
                base, quote = exchange_trading_pair[:-len(quote_asset)], exchange_trading_pair[-len(quote_asset):]
                break
    return base, quote


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    base, quote = "", ""
    if "-" in exchange_trading_pair:
        return exchange_trading_pair
    if "/" in exchange_trading_pair:
        base, quote = exchange_trading_pair.split("/")
    else:
        base, quote = split_to_base_quote(exchange_trading_pair)
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
