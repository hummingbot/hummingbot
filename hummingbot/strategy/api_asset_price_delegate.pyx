from hummingbot.data_feed.custom_api_data_feed import CustomAPIDataFeed, NetworkStatus
from .asset_price_delegate cimport AssetPriceDelegate

cdef class APIAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, api_url: str):
        super().__init__()
        self._custom_api_feed = CustomAPIDataFeed(api_url=api_url)
        self._custom_api_feed.start()

    cdef object c_get_mid_price(self):
        return self._custom_api_feed.get_price()

    @property
    def ready(self) -> bool:
        return self._custom_api_feed.network_status == NetworkStatus.CONNECTED

    @property
    def custom_api_feed(self) -> CustomAPIDataFeed:
        return self._custom_api_feed
