from .asset_price_delegate cimport AssetPriceDelegate
from hummingbot.connector.exchange_base cimport ExchangeBase

cdef class APIAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        ExchangeBase _market
        object _custom_api_feed
