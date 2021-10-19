from hummingbot.connector.exchange_base cimport ExchangeBase
from .asset_price_delegate cimport AssetPriceDelegate

cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        ExchangeBase _market
        str _trading_pair
