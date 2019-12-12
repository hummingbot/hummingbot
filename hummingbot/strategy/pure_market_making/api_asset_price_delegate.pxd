from .asset_price_delegate cimport AssetPriceDelegate

cdef class APIAssetPriceDelegate(AssetPriceDelegate):
    cdef object c_get_mid_price(self)
