from wings.market.market_base import (
    MarketBase,
    OrderType
)
from wings.time_iterator cimport TimeIterator

NaN = float("nan")


cdef class Strategy(TimeIterator):
    def __init__(self, market: MarketBase):
        super().__init__()
        self._market = market

    @property
    def market(self) -> MarketBase:
        return self._market

    cdef c_buy(self, object symbol, double amount, object order_type=OrderType.MARKET, double price = NaN):
        return self._market.c_buy(symbol, amount, order_type=order_type, price=price)

    cdef c_sell(self, object symbol, double amount, object order_type=OrderType.MARKET, double price = NaN):
        return self._market.c_sell(symbol, amount, order_type=order_type, price=price)

    def buy(self, symbol: str, amount: float, order_type: OrderType = OrderType.MARKET, price: float = NaN):
        return self.c_buy(symbol, amount, order_type=order_type, price=price)

    def sell(self, symbol: str, amount: float, order_type: OrderType = OrderType.MARKET, price: float = NaN):
        return self.c_sell(symbol, amount, order_type=order_type, price=price)
