from collections import OrderedDict

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.strategy.maker_taker_market_pair import MakerTakerMarketPair

s_float_nan = float("nan")


cdef class OrderIDMarketPairTrackingItem:
    cdef:
        public str order_id
        public object exchange
        public object market_pair
        public double expiry_timestamp

    def __init__(self, str order_id, object exchange, object market_pair):
        self.order_id = order_id
        self.exchange = exchange
        self.market_pair = market_pair
        self.expiry_timestamp = s_float_nan

cdef class OrderIDMarketPairTracker(TimeIterator):
    def __init__(self, double expiry_timeout=3 * 60):
        super().__init__()

        self._order_id_to_tracking_item = OrderedDict()
        self._expiry_timeout = expiry_timeout

    cdef c_tick(self, double timestamp):
        TimeIterator.c_tick(self, timestamp)
        self.c_check_and_expire_tracking_items()

    cdef object c_get_market_pair_from_order_id(self, str order_id):
        cdef:
            OrderIDMarketPairTrackingItem item = self._order_id_to_tracking_item.get(order_id)

        if item is not None:
            return item.market_pair
        return None

    def get_market_pair_from_order_id(self, order_id: str):
        return self.c_get_market_pair_from_order_id(order_id)

    cdef object c_get_exchange_from_order_id(self, str order_id):
        cdef:
            OrderIDMarketPairTrackingItem item = self._order_id_to_tracking_item.get(order_id)

        if item is not None:
            return item.exchange
        return None

    def get_exchange_from_order_id(self, order_id: str):
        return self.c_get_exchange_from_order_id(order_id)

    cdef c_start_tracking_order_id(self, str order_id, object exchange, object market_pair):
        self._order_id_to_tracking_item[order_id] = OrderIDMarketPairTrackingItem(order_id, exchange, market_pair)

    def start_tracking_order_id(self, order_id: str, exchange: ExchangeBase, market_pair: MakerTakerMarketPair):
        self.c_start_tracking_order_id(order_id, exchange, market_pair)

    cdef c_stop_tracking_order_id(self, str order_id):
        cdef:
            OrderIDMarketPairTrackingItem item = self._order_id_to_tracking_item.get(order_id)

        if item is None:
            return
        item.expiry_timestamp = self._current_timestamp + self._expiry_timeout

    def stop_tracking_order_id(self, order_id: str):
        self.c_stop_tracking_order_id(order_id)

    cdef c_check_and_expire_tracking_items(self):
        cdef:
            list order_ids_to_delete = []
            OrderIDMarketPairTrackingItem typed_tracking_item

        for order_id, tracking_item in self._order_id_to_tracking_item.items():
            typed_tracking_item = tracking_item
            if self._current_timestamp > typed_tracking_item.expiry_timestamp:
                order_ids_to_delete.append(order_id)
            else:
                break

        for order_id in order_ids_to_delete:
            del self._order_id_to_tracking_item[order_id]

    def check_and_expire_tracking_items(self):
        self.c_check_and_expire_tracking_items()
