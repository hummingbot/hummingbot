from typing import List
from decimal import Decimal
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple

from .data_types import (
    PricingProposal
)
from .pure_market_making_v2 import PureMarketMakingStrategyV2

cdef class OrderPricingDelegate:
    # The following exposed Python functions are meant for unit tests
    # ---------------------------------------------------------------
    def get_order_price_proposal(self,
                                 strategy: PureMarketMakingStrategyV2,
                                 market_info: MarketTradingPairTuple,
                                 active_orders: List[LimitOrder],
                                 asset_mid_price: Decimal) -> PricingProposal:
        return self.c_get_order_price_proposal(strategy, market_info, active_orders, asset_mid_price)
    # ---------------------------------------------------------------

    cdef object c_get_order_price_proposal(self,
                                           PureMarketMakingStrategyV2 strategy,
                                           object market_info,
                                           list active_orders,
                                           object asset_mid_price):
        raise NotImplementedError
