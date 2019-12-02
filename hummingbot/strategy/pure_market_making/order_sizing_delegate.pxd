from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class OrderSizingDelegate:
    cdef object c_get_order_size_proposal(self,
                                          PureMarketMakingStrategyV2 strategy,
                                          object market_info,
                                          list active_orders,
                                          object pricing_proposal)
