from .asset_price_delegate cimport AssetPriceDelegate

cdef class DataFeedAssetPriceDelegate(AssetPriceDelegate):
    cdef:
        str _base_asset
        str _quote_asset
