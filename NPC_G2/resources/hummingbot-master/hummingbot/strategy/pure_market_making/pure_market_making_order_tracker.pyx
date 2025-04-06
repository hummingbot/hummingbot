from typing import (
    Dict,
    List,
    Tuple
)

from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.connector.connector_base import ConnectorBase
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.order_tracker cimport OrderTracker

NaN = float("nan")


cdef class PureMarketMakingOrderTracker(OrderTracker):
    # ETH confirmation requirement of Binance has shortened to 12 blocks as of 7/15/2019.
    # 12 * 15 / 60 = 3 minutes
    SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION = 60.0 * 3

    def __init__(self):
        super().__init__()

    @property
    def active_limit_orders(self) -> List[Tuple[ConnectorBase, LimitOrder]]:
        limit_orders = []
        for market_pair, orders_map in self._tracked_limit_orders.items():
            for limit_order in orders_map.values():
                limit_orders.append((market_pair.market, limit_order))
        return limit_orders

    @property
    def shadow_limit_orders(self) -> List[Tuple[ConnectorBase, LimitOrder]]:
        limit_orders = []
        for market_pair, orders_map in self._shadow_tracked_limit_orders.items():
            for limit_order in orders_map.values():
                limit_orders.append((market_pair.market, limit_order))
        return limit_orders

    @property
    def market_pair_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        market_pair_to_orders = {}
        market_pairs = self._tracked_limit_orders.keys()
        for market_pair in market_pairs:
            maker_orders = []
            for limit_order in self._tracked_limit_orders[market_pair].values():
                maker_orders.append(limit_order)
            market_pair_to_orders[market_pair] = maker_orders
        return market_pair_to_orders
