from .asset_price_delegate cimport AssetPriceDelegate
from hummingbot.connector.exchange_base cimport ExchangeBase

cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        ExchangeBase _market
        str _trading_pair
