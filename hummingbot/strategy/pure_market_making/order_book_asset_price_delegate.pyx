from .asset_price_delegate cimport AssetPriceDelegate
from hummingbot.market.market_base import MarketBase
from decimal import Decimal

cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, market: MarketBase, trading_pair: str):
        super().__init__()
        self._market = market
        self._trading_pair = trading_pair

    cdef object c_get_mid_price(self):
        return (self._market.c_get_price(self._trading_pair, True) +
                self._market.c_get_price(self._trading_pair, False))/Decimal('2')

    @property
    def ready(self) -> bool:
        return self._market.ready
