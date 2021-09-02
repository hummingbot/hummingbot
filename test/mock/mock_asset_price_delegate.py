from decimal import Decimal

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.event.events import PriceType
from hummingbot.strategy.asset_price_delegate import AssetPriceDelegate


class MockAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, market: ExchangeBase, mock_price: Decimal):
        self._market = market
        self._mock_price = mock_price

    def set_mock_price(self, mock_price: Decimal):
        self._mock_price = mock_price

    def get_mid_price(self) -> Decimal:
        return self.c_get_mid_price()

    def get_price_by_type(self, _: PriceType) -> Decimal:
        return self.c_get_mid_price()

    def c_get_mid_price(self):
        return self._mock_price

    def ready(self) -> bool:
        return True

    def market(self) -> ExchangeBase:
        return self._market
