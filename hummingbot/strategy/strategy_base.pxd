from hummingbot.core.time_iterator cimport TimeIterator

cdef class StrategyBase(TimeIterator):
    cdef:
        set _markets
        double _limit_order_min_expiration
        bint _delegate_lock

    cdef c_buy_with_specific_market(self, object market_symbol_pair, double amount,
                                    object order_type = *, double price = *, double expiration_seconds = *)
    cdef c_sell_with_specific_market(self, object market_symbol_pair, double amount,
                                     object order_type = *, double price = *, double expiration_seconds = *)