from hummingbot.connector.exchange_base cimport ExchangeBase
from .asset_price_delegate cimport AssetPriceDelegate

cdef class APIAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        ExchangeBase _market
        object _custom_api_feed
