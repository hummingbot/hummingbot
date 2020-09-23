import math

from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from hummingbot.connector.exchange.bitfinex import TRADING_PAIR_SPLITTER


# deeply merge two dictionaries
def merge_dicts(source: Dict, destination: Dict) -> Dict:
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dicts(value, node)
        else:
            destination[key] = value

    return destination


# join paths
def join_paths(*paths: List[str]) -> str:
    return "/".join(paths)


# get precision decimal from a number
def get_precision(precision: int) -> Decimal:
    return Decimal(1) / Decimal(math.pow(10, precision))


def split_trading_pair(trading_pair: str) -> Tuple[str, str]:
    try:
        base, quote = trading_pair.split("-")
        return base, quote
    # exceptions are now logged as warnings in trading pair fetcher
    except Exception as e:
        raise e


def split_trading_pair_from_exchange(trading_pair: str) -> Tuple[str, str]:
    try:
        # sometimes the exchange returns trading pairs like tBTCUSD
        isTradingPair = trading_pair[0].islower() and trading_pair[1].isupper()

        m: Tuple[str, str] = (None, None)

        if isTradingPair:
            m = TRADING_PAIR_SPLITTER.match(trading_pair[1:])
        else:
            m = TRADING_PAIR_SPLITTER.match(trading_pair)

        return m.group(1), m.group(2)
    # exceptions are now logged as warnings in trading pair fetcher
    except Exception as e:
        raise e


def valid_exchange_trading_pair(trading_pair: str) -> bool:
    try:
        base, quote = split_trading_pair_from_exchange(trading_pair)
        return True
    except Exception:
        return False


def convert_from_exchange_trading_pair(exchange_trading_pair: str) -> Optional[str]:
    try:
        # exchange does not split BASEQUOTE (BTCUSDT)
        base_asset, quote_asset = split_trading_pair_from_exchange(exchange_trading_pair)
        return f"{base_asset}-{quote_asset}"
    except Exception as e:
        raise e


def convert_to_exchange_trading_pair(hb_trading_pair: str) -> str:
    # exchange does not split BASEQUOTE (BTCUSDT)
    return hb_trading_pair.replace("-", "")
