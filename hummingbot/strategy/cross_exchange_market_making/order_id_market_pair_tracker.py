from collections import OrderedDict
from decimal import Decimal

s_float_nan = float("nan")


class OrderIDMarketPairTrackingItem:
    def __init__(self, order_id: str, exchange, market_pair):
        self.order_id = order_id
        self.exchange = exchange
        self.market_pair = market_pair
        self.expiry_timestamp = s_float_nan


class OrderIDMarketPairTracker():
    def __init__(self, expiry_timeout: Decimal = 3 * 60):
        super().__init__()

        self._order_id_to_tracking_item = OrderedDict()
        self._expiry_timeout = expiry_timeout

    def tick(self, timestamp: Decimal):
        self.check_and_expire_tracking_items(timestamp)

    def get_market_pair_from_order_id(self, order_id: str):
        item = self._order_id_to_tracking_item.get(order_id)

        if item is not None:
            return item.market_pair
        return None

    def get_exchange_from_order_id(self, order_id: str):
        item = self._order_id_to_tracking_item.get(order_id)

        if item is not None:
            return item.exchange
        return None

    def start_tracking_order_id(self, order_id: str, exchange, market_pair):
        self._order_id_to_tracking_item[order_id] = OrderIDMarketPairTrackingItem(order_id, exchange, market_pair)

    def stop_tracking_order_id(self, order_id: str):
        item = self._order_id_to_tracking_item.get(order_id)

        if item is None:
            return
        item.expiry_timestamp = self._current_timestamp + self._expiry_timeout

    def check_and_expire_tracking_items(self, timestamp: Decimal):
        order_ids_to_delete = []

        for order_id, tracking_item in self._order_id_to_tracking_item.items():
            typed_tracking_item = tracking_item
            if timestamp > typed_tracking_item.expiry_timestamp:
                order_ids_to_delete.append(order_id)
            else:
                break

        for order_id in order_ids_to_delete:
            del self._order_id_to_tracking_item[order_id]
