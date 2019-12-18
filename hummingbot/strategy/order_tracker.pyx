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
from .market_trading_pair_tuple import MarketTradingPairTuple

NaN = float("nan")

cdef class OrderTracker(TimeIterator):
    # ETH confirmation requirement of Binance has shortened to 12 blocks as of 7/15/2019.
    # 12 * 15 / 60 = 3 minutes
    SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION = 60.0 * 3

    CANCEL_EXPIRY_DURATION = 60.0

    def __init__(self):
        super().__init__()
        self._tracked_maker_orders = {}
        self._tracked_taker_orders = {}
        self._order_id_to_market_pair = {}
        self._shadow_tracked_maker_orders = {}
        self._shadow_order_id_to_market_pair = {}
        self._shadow_gc_requests = deque()
        self._in_flight_pending_created = set()
        self._in_flight_cancels = OrderedDict()

    @property
    def active_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        maker_orders = []
        for market_pair, orders_map in self._tracked_maker_orders.items():
            for limit_order in orders_map.values():
                if self.c_has_in_flight_cancel(limit_order.client_order_id):
                    continue
                maker_orders.append((market_pair.market, limit_order))
        return maker_orders

    @property
    def shadow_maker_orders(self) -> List[Tuple[MarketBase, LimitOrder]]:
        maker_orders = []
        for market_pair, orders_map in self._shadow_tracked_maker_orders.items():
            for limit_order in orders_map.values():
                if self.c_has_in_flight_cancel(limit_order.client_order_id):
                    continue
                maker_orders.append((market_pair.market, limit_order))
        return maker_orders

    @property
    def market_pair_to_active_orders(self) -> Dict[MarketTradingPairTuple, List[LimitOrder]]:
        market_pair_to_orders = {}
        market_pairs = self._tracked_maker_orders.keys()
        for market_pair in market_pairs:
            maker_orders = []
            for limit_order in self._tracked_maker_orders[market_pair].values():
                if self.c_has_in_flight_cancel(limit_order.client_order_id):
                    continue
                maker_orders.append(limit_order)
            market_pair_to_orders[market_pair] = maker_orders
        return market_pair_to_orders

    @property
    def active_bids(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if limit_order.is_buy]

    @property
    def active_asks(self) -> List[Tuple[MarketBase, LimitOrder]]:
        return [(market, limit_order) for market, limit_order in self.active_maker_orders if not limit_order.is_buy]

    @property
    def tracked_taker_orders(self) -> List[Tuple[MarketBase, MarketOrder]]:
        return [(market_trading_pair_tuple[0], order) for market_trading_pair_tuple, order_map in self._tracked_taker_orders.items()
                for order in order_map.values()]

    @property
    def tracked_taker_orders_data_frame(self) -> List[pd.DataFrame]:
        market_orders = [[market_trading_pair_tuple.market.display_name, market_trading_pair_tuple.trading_pair, order_id, order.amount,
                          pd.Timestamp(order.timestamp, unit='s', tz='UTC').strftime('%Y-%m-%d %H:%M:%S')
                          ]
                         for market_trading_pair_tuple, order_map in self._tracked_taker_orders.items()
                         for order_id, order in order_map.items()]

        return pd.DataFrame(data=market_orders, columns=["market", "trading_pair", "order_id", "quantity", "timestamp"])

    @property
    def in_flight_cancels(self) -> Dict[str, float]:
        return self._in_flight_cancels

    @property
    def in_flight_pending_created(self) -> Dict[str, float]:
        return self._in_flight_pending_created

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        self.c_check_and_cleanup_shadow_records()

    cdef dict c_get_maker_orders(self):
        return self._tracked_maker_orders

    cdef dict c_get_taker_orders(self):
        return self._tracked_taker_orders

    cdef dict c_get_shadow_maker_orders(self):
        return self._shadow_tracked_maker_orders

    cdef bint c_has_in_flight_cancel(self, str order_id):
        return self._in_flight_cancels.get(order_id, NaN) + self.CANCEL_EXPIRY_DURATION > self._current_timestamp

    cdef bint c_check_and_track_cancel(self, str order_id):
        """
        :param order_id: the order id to be cancelled
        :return: True if there's no existing in flight cancel for the order id, False otherwise.
        """
        cdef:
            list keys_to_delete = []

        if order_id in self._in_flight_pending_created:  # Checks if a Buy/SellOrderCreatedEvent has been received
            return False

        # Maintain the cancel expiry time invariant.
        for k, cancel_timestamp in self._in_flight_cancels.items():
            if cancel_timestamp < self._current_timestamp - self.CANCEL_EXPIRY_DURATION:
                keys_to_delete.append(k)
        for k in keys_to_delete:
            del self._in_flight_cancels[k]

        if order_id in self.in_flight_cancels:
            return False

        # Track the cancel.
        self._in_flight_cancels[order_id] = self._current_timestamp
        return True

    cdef object c_get_market_pair_from_order_id(self, str order_id):
        return self._order_id_to_market_pair.get(order_id)

    cdef object c_get_shadow_market_pair_from_order_id(self, str order_id):
        return self._shadow_order_id_to_market_pair.get(order_id)

    cdef LimitOrder c_get_limit_order(self, object market_pair, str order_id):
        return self._tracked_maker_orders.get(market_pair, {}).get(order_id)

    cdef object c_get_market_order(self, object market_pair, str order_id):
        return self._tracked_taker_orders.get(market_pair, {}).get(order_id)

    cdef LimitOrder c_get_shadow_limit_order(self, str order_id):
        cdef:
            object market_pair = self._shadow_order_id_to_market_pair.get(order_id)

        return self._shadow_tracked_maker_orders.get(market_pair, {}).get(order_id)

    cdef c_start_tracking_limit_order(self, object market_pair, str order_id, bint is_buy, object price,
                                      object quantity):
        if market_pair not in self._tracked_maker_orders:
            self._tracked_maker_orders[market_pair] = {}
        if market_pair not in self._shadow_tracked_maker_orders:
            self._shadow_tracked_maker_orders[market_pair] = {}

        cdef:
            LimitOrder limit_order = LimitOrder(order_id,
                                                market_pair.trading_pair,
                                                is_buy,
                                                market_pair.base_asset,
                                                market_pair.quote_asset,
                                                price,
                                                quantity)
        self._tracked_maker_orders[market_pair][order_id] = limit_order
        self._shadow_tracked_maker_orders[market_pair][order_id] = limit_order
        self._order_id_to_market_pair[order_id] = market_pair
        self._shadow_order_id_to_market_pair[order_id] = market_pair

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

    cdef c_start_tracking_market_order(self, object market_pair, str order_id, bint is_buy, object quantity):
        if market_pair not in self._tracked_taker_orders:
            self._tracked_taker_orders[market_pair] = {}
        self._tracked_taker_orders[market_pair][order_id] = MarketOrder(
            order_id,
            market_pair.trading_pair,
            is_buy,
            market_pair.base_asset,
            market_pair.quote_asset,
            float(quantity),
            self._current_timestamp
        )
        self._order_id_to_market_pair[order_id] = market_pair

    cdef c_stop_tracking_market_order(self, object market_pair, str order_id):
        if market_pair in self._tracked_taker_orders and order_id in self._tracked_taker_orders[market_pair]:
            del self._tracked_taker_orders[market_pair][order_id]
            if len(self._tracked_taker_orders[market_pair]) < 1:
                del self._tracked_taker_orders[market_pair]
        if order_id in self._order_id_to_market_pair:
            del self._order_id_to_market_pair[order_id]

    cdef c_check_and_cleanup_shadow_records(self):
        cdef:
            double current_timestamp = self._current_timestamp

        while len(self._shadow_gc_requests) > 0 and self._shadow_gc_requests[0][0] < current_timestamp:
            _, market_pair, order_id = self._shadow_gc_requests.popleft()
            if (market_pair in self._shadow_tracked_maker_orders and
                    order_id in self._shadow_tracked_maker_orders[market_pair]):
                del self._shadow_tracked_maker_orders[market_pair][order_id]
                if len(self._shadow_tracked_maker_orders[market_pair]) < 1:
                    del self._shadow_tracked_maker_orders[market_pair]
            if order_id in self._shadow_order_id_to_market_pair:
                del self._shadow_order_id_to_market_pair[order_id]

    cdef c_add_create_order_pending(self, str order_id):
        self.in_flight_pending_created.add(order_id)

    cdef c_remove_create_order_pending(self, str order_id):
        self._in_flight_pending_created.discard(order_id)
