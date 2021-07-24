from decimal import Decimal

from hummingbot.core.event.events import PriceType
from .asset_price_delegate cimport AssetPriceDelegate
from hummingbot.data_feed.custom_api_data_feed import CustomAPIDataFeed, NetworkStatus

cdef class APIAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, api_url: str, update_interval: float):
        super().__init__()
        self._custom_api_feed = CustomAPIDataFeed(api_url=api_url, update_interval=update_interval)
        self._custom_api_feed.start()

    cdef object c_get_mid_price(self):
        return self._custom_api_feed.get_price()

    def get_price_by_type(self, _: PriceType) -> Decimal:
        return self.c_get_mid_price()

    @property
    def ready(self) -> bool:
        return self._custom_api_feed.network_status == NetworkStatus.CONNECTED

    @property
    def custom_api_feed(self) -> CustomAPIDataFeed:
        return self._custom_api_feed
