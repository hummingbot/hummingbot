from typing import NamedTuple

from hummingbot.market import MarketBase


class MarketSymbolPair(NamedTuple):
    market: MarketBase
    trading_pair: str
    base_asset: str
    quote_asset: str
