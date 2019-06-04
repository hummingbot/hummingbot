cdef class OrderPricingDelegate:
    cdef object c_get_order_price_proposal(self, PureMarketMakingStrategyV2 strategy, object market_info):
        raise NotImplementedError
