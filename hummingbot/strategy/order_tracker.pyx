from collections import (
    deque,
    OrderedDict
)

from hummingbot.core.data_type.limit_order cimport LimitOrder
from hummingbot.core.data_type.market_order import MarketOrder


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

        # TODO: refactor the in flight cancel logic from strategies.
        self._in_flight_cancels = OrderedDict()

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        self.c_check_and_cleanup_shadow_records()

    cdef dict c_get_maker_orders(self):
        return self._tracked_maker_orders

    cdef dict c_get_taker_orders(self):
        return self._tracked_taker_orders

    cdef dict c_get_shadow_maker_orders(self):
        return self._shadow_tracked_maker_orders

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
        if order_id in self._order_id_to_market_pair:
            del self._order_id_to_market_pair[order_id]
        self._shadow_gc_requests.append((
            self._current_timestamp + self.SHADOW_MAKER_ORDER_KEEP_ALIVE_DURATION,
            market_pair,
            order_id
        ))


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
