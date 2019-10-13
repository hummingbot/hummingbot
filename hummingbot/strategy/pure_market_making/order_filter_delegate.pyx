from typing import List

from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from .data_types import (
    OrdersProposal
)
from .pure_market_making_v2 import PureMarketMakingStrategyV2

from hummingbot.core.data_type.limit_order import LimitOrder


cdef class OrderFilterDelegate:

    def __init__(self, order_placing_timestamp: float = 0):
        self._order_placing_timestamp = order_placing_timestamp

    @property
    def order_placing_timestamp(self) -> float:
        return self._order_placing_timestamp

    @order_placing_timestamp.setter
    def order_placing_timestamp(self, double order_placing_timestamp):
        self._order_placing_timestamp = order_placing_timestamp

    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def should_proceed_with_processing(self,
                                       strategy: PureMarketMakingStrategyV2,
                                       market_info: MarketTradingPairTuple,
                                       active_orders: List[LimitOrder]) -> bool:
        return self.c_should_proceed_with_processing(strategy, market_info, active_orders)

    def filter_orders_proposal(self,
                               strategy: PureMarketMakingStrategyV2,
                               market_info: MarketTradingPairTuple,
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
