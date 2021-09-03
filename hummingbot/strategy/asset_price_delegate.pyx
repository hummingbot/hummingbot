from decimal import Decimal

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.core.event.events import PriceType

cdef class AssetPriceDelegate:
    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def get_mid_price(self) -> Decimal:
        return self.c_get_mid_price()
    # ---------------------------------------------------------------

    def get_price_by_type(self, price_type: PriceType) -> Decimal:
        raise NotImplementedError

    cdef object c_get_mid_price(self):
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        raise NotImplementedError

    @property
    def market(self) -> ExchangeBase:
        raise NotImplementedError
