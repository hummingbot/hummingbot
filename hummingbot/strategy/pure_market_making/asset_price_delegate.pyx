from decimal import Decimal
from .pure_market_making_v2 import PureMarketMakingStrategyV2


cdef class AssetPriceDelegate :
    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def get_mid_price(self) -> Decimal:
        return self.c_get_mid_price()
    # ---------------------------------------------------------------

    cdef object c_get_mid_price(self):
        raise NotImplementedError

    @property
    def ready(self) -> bool:
        raise NotImplementedError
