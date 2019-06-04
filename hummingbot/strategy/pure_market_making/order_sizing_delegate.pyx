cdef class OrderSizingDelegate:
    cdef object c_get_order_size_proposal(self, PureMarketMakingStrategyV2 strategy, object market_info):
        raise NotImplementedError
