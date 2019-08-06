from collections import (
    deque,
    OrderedDict
)
import pandas as pd
from typing import (
    Dict,
    List,
    Tuple
)

from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder
from hummingbot.market.market_base import MarketBase
from hummingbot.strategy.market_symbol_pair import MarketSymbolPair
from hummingbot.strategy.order_tracker import OrderTracker
from hummingbot.strategy.order_tracker cimport OrderTracker

NaN = float("nan")


cdef class PureMarketMakingOrderTracker(OrderTracker):
    # ETH confirmation requirement of Binance has shortened to 12 blocks as of 7/15/2019.
    # 12 * 15 / 60 = 3 minutes
    SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION = 60.0 * 3

    def __init__(self):
        super().__init__()

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        maker_orders = []
        for market_pair, orders_map in self._tracked_maker_orders.items():
            for limit_order in orders_map.values():
                maker_orders.append((market_pair.market, limit_order))
        return maker_orders

    @property
    def shadow_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        maker_orders = []
        for market_pair, orders_map in self._shadow_tracked_maker_orders.items():
            for limit_order in orders_map.values():
                maker_orders.append((market_pair.market, limit_order))
        return maker_orders

    @property
    def market_pair_to_active_orders(self) -> Dict[MarketSymbolPair, List[LimitOrder]]:
        market_pair_to_orders = {}
        market_pairs = self._tracked_maker_orders.keys()
        for market_pair in market_pairs:
            maker_orders = []
            for limit_order in self._tracked_maker_orders[market_pair].values():
                maker_orders.append(limit_order)
            market_pair_to_orders[market_pair] = maker_orders
        return market_pair_to_orders

    cdef bint c_check_and_track_cancel(self, str order_id):
        """
        :param order_id: the order id to be cancelled
        :return: True if there's no existing in flight cancel for the order id, False otherwise.
        """
        if order_id in self._in_flight_cancels:
            return False

        # Track the cancel.
        self._in_flight_cancels[order_id] = self._current_timestamp
        return True

    cdef c_stop_tracking_limit_order(self, object market_pair, str order_id):
        if market_pair in self._tracked_maker_orders and order_id in self._tracked_maker_orders[market_pair]:
            del self._tracked_maker_orders[market_pair][order_id]
            if len(self._tracked_maker_orders[market_pair]) < 1:
                del self._tracked_maker_orders[market_pair]
            self._shadow_gc_requests.append((
                self._current_timestamp + self.SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION,
                market_pair,
                order_id
            ))

        if order_id in self._order_id_to_market_pair:
            del self._order_id_to_market_pair[order_id]
        if order_id in self._in_flight_cancels:
            del self._in_flight_cancels[order_id]
