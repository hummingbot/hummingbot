from .asset_price_delegate cimport AssetPriceDelegate
from hummingbot.core.utils.exchange_rate_conversion import ExchangeRateConversion

cdef class DataFeedAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, base_asset: str, quote_asset: str):
        super().__init__()
        self._base_asset = base_asset
        self._quote_asset = quote_asset

    cdef object c_get_mid_price(self):
        ex_rate_conversion = ExchangeRateConversion.get_instance()
        return ex_rate_conversion.convert_token_value_decimal(1, self._base_asset, self._quote_asset)

    @property
    def ready(self) -> bool:
        return ExchangeRateConversion.get_instance().ready
