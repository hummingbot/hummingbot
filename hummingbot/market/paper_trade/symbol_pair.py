from typing import NamedTuple


class SymbolPair(NamedTuple):
    trading_pair: str
    base_asset: str
    quote_asset: str
