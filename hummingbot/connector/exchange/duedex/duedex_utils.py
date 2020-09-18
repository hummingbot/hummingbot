import re
import time
from typing import (
    Optional,
    Tuple)
from datetime import datetime
TRADING_PAIR_SPLITTER = re.compile(r"^(\w+)(USD|USDT|BTC|ETH)$")


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
    # Duedex uses uppercase (BTCUSD)
    base_asset, quote_asset = split_trading_pair(exchange_trading_pair)
    return f"{base_asset.upper()}-{quote_asset.upper()}"


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # Duedex uses uppercase (BTCUSD)
    return hb_trading_pair.replace("-", "").upper()


def string_timestamp_to_seconds(timestamp: str) -> datetime:
    dt = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    return time.mktime(dt.timetuple())
