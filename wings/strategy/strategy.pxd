from wings.market.market_base cimport MarketBase
from wings.time_iterator cimport TimeIterator


cdef class Strategy(TimeIterator):
    cdef:
        MarketBase _market

    cdef c_tick(self, double timestamp)
    cdef c_buy(self, object symbol, double amount, object order_type=*, double price=*)
    cdef c_sell(self, object symbol, double amount, object order_type=*, double price=*)