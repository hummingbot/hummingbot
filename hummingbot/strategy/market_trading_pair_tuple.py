from typing import NamedTuple

from hummingbot.market.market_base import MarketBase


class MarketTradingPairTuple(NamedTuple):
    market: MarketBase
    trading_pair: str
    base_asset: str
    quote_asset: str

    @property
    def order_book(self):
        return self.market.get_order_book(self.trading_pair)

    @property
    def quote_balance(self):
        return self.market.get_balance(self.quote_asset)

    @property
    def base_balance(self):
        return self.market.get_balance(self.base_asset)
