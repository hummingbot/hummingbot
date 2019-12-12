from .asset_price_delegate cimport AssetPriceDelegate

cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        object _market_info
