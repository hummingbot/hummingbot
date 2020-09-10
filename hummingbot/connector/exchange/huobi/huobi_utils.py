import re
from typing import (
    Optional,
    Tuple)
TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(usdt|husd|btc|eth|ht|trx)$")


def split_trading_pair(trading_pair: str) -> Optional[Tuple[str, str]]:
    try:
        m = TRADING_PAIR_SPLITTER.match(trading_pair)
        return m.group(1), m.group(2)
    # Exceptions are now logged as warnings in trading pair fetcher
    except Exception:
        return None


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    if split_trading_pair(exchange_trading_pair) is None:
        return None
    # Huobi uses lowercase (btcusdt)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Huobi uses lowercase (btcusdt)
    return hb_trading_pair.replace("-", "").lower()
