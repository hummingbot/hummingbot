from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class OrderFilterDelegate:
    cdef bint c_should_proceed_with_processing(self,
                                               PureMarketMakingStrategyV2 strategy,
                                               object market_info) except? False
    cdef object c_filter_orders_proposal(self,
                                         PureMarketMakingStrategyV2 strategy,
                                         object market_info,
                                         object orders_proposal)
