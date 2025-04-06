from hummingbot.core.data_type.common import PriceType
from hummingbot.connector.exchange_base import ExchangeBase
from decimal import Decimal
from .asset_price_delegate cimport AssetPriceDelegate

cdef class OrderBookAssetPriceDelegate(AssetPriceDelegate):
    def __init__(self, market: ExchangeBase, trading_pair: str):
        super().__init__()
        self._market = market
        self._trading_pair = trading_pair

    cdef object c_get_mid_price(self):
        return (self._market.c_get_price(self._trading_pair, True) +
                self._market.c_get_price(self._trading_pair, False))/Decimal('2')

    @property
    def ready(self) -> bool:
        return self._market.ready

    def get_price_by_type(self, price_type: PriceType) -> Decimal:
        return self._market.get_price_by_type(self._trading_pair, price_type)

    @property
    def market(self) -> ExchangeBase:
        return self._market

    @property
    def trading_pair(self) -> str:
        return self._trading_pair
