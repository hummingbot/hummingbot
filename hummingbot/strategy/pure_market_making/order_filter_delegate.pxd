from .pure_market_making_v2 cimport PureMarketMakingStrategyV2


cdef class OrderFilterDelegate:
    cdef:
        double _order_placing_timestamp

    cdef bint c_should_proceed_with_processing(self,
                                               PureMarketMakingStrategyV2 strategy,
                                               object market_info,
                                               list active_orders) except? True
    cdef object c_filter_orders_proposal(self,
                                         PureMarketMakingStrategyV2 strategy,
                                         object market_info,
                                         list active_orders,
                                         object orders_proposal)
