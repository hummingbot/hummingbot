from .asset_price_delegate cimport AssetPriceDelegate

cdef class APIAssetPriceDelegate(AssetPriceDelegate):
    cdef object _custom_api_feed
