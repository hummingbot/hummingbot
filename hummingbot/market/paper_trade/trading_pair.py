from typing import NamedTuple


class TradingPair(NamedTuple):
    trading_pair: str
    base_asset: str
    quote_asset: str
