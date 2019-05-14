from typing import NamedTuple

from wings.market.market_base import MarketBase


class MarketSymbolPair(NamedTuple):
    market: MarketBase
    trading_pair: str
    base_asset: str
    quote_asset: str
