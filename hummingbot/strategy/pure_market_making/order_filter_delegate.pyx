from typing import List

from .data_types import (
    MarketInfo,
    OrdersProposal
)
from .pure_market_making_v2 import PureMarketMakingStrategyV2

from hummingbot.core.data_type.limit_order import LimitOrder


cdef class OrderFilterDelegate:
    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def should_proceed_with_processing(self,
                                       strategy: PureMarketMakingStrategyV2,
                                       market_info: MarketInfo,
                                       active_orders: List[LimitOrder]) -> bool:
        return self.c_should_proceed_with_processing(strategy, market_info, active_orders)

    def filter_orders_proposal(self,
                               strategy: PureMarketMakingStrategyV2,
                               market_info: MarketInfo,
                               active_orders: List[LimitOrder],
                               orders_proposal: OrdersProposal
                               ):
        return self.c_filter_orders_proposal(strategy, market_info, active_orders, orders_proposal)
    # ---------------------------------------------------------------

    cdef bint c_should_proceed_with_processing(self,
                                               PureMarketMakingStrategyV2 strategy,
                                               object market_info,
                                               list active_orders) except? True:
        raise NotImplementedError

    cdef object c_filter_orders_proposal(self,
                                         PureMarketMakingStrategyV2 strategy,
                                         object market_info,
                                         list active_orders,
                                         object orders_proposal):
        raise NotImplementedError
