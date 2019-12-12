from .asset_price_delegate cimport AssetPriceDelegate
from hummingbot.market.paper_trade import create_paper_trade_market
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, market_info: MarketTradingPairTuple):
        super().__init__()
        self._market_info = market_info

    cdef object c_get_mid_price(self):
        return self._market_info.get_mid_price()
