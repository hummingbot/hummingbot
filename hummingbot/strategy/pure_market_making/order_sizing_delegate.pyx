from typing import List

from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from .data_types import (
    SizingProposal,
    PricingProposal,
)
from .pure_market_making_v2 import PureMarketMakingStrategyV2


cdef class OrderSizingDelegate:
    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def get_order_size_proposal(self,
                                strategy: PureMarketMakingStrategyV2,
                                market_info: MarketTradingPairTuple,
                                active_orders: List[LimitOrder],
                                pricing_proposal: PricingProposal) -> SizingProposal:
        return self.c_get_order_size_proposal(strategy, market_info, active_orders, pricing_proposal)
    # ---------------------------------------------------------------

    cdef object c_get_order_size_proposal(self,
                                          PureMarketMakingStrategyV2 strategy,
                                          object market_info,
                                          list active_orders,
                                          object pricing_proposal):
        raise NotImplementedError
