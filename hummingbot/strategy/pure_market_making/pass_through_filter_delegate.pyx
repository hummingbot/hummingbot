from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class PassThroughFilterDelegate(OrderFilterDelegate):
    cdef bint c_should_proceed_with_processing(self,
                                               PureMarketMakingStrategyV2 strategy,
                                               object market_info,
                                               list active_orders) except? True:
        return True

    cdef object c_filter_orders_proposal(self,
                                         PureMarketMakingStrategyV2 strategy,
                                         object market_info,
                                         object orders_proposal):
        return orders_proposal