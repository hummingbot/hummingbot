from .asset_price_delegate cimport AssetPriceDelegate

cdef class APIAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self):
        super().__init__()

    cdef object c_get_mid_price(self):
        return 3

    @property
    def ready(self) -> bool:
        return True