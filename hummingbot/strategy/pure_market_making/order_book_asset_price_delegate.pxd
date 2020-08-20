from .asset_price_delegate cimport AssetPriceDelegate
from hummingbot.market.market_base cimport MarketBase

cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        MarketBase _market
        str _trading_pair
