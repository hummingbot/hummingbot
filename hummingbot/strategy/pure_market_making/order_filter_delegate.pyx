cdef class OrderFilterDelegate:
    cdef bint c_should_proceed_with_processing(self,
                                               PureMarketMakingStrategyV2 strategy,
                                               object market_info) except? False:
        raise NotImplementedError

    cdef object c_filter_orders_proposal(self,
                                         PureMarketMakingStrategyV2 strategy,
                                         object market_info,
                                         object orders_proposal):
        raise NotImplementedError
