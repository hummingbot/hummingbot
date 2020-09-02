# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging
import numpy as np

from decimal import Decimal
from typing import Dict
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
CryptoComOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]

cdef class CryptoComActiveOrderTracker:
    def __init__(self,
                 active_asks: CryptoComOrderBookTrackingDictionary = None,
                 active_bids: CryptoComOrderBookTrackingDictionary = None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger
        if _logger is None:
            _logger = logging.getLogger(__name__)
        return _logger

    @property
    def active_asks(self) -> CryptoComOrderBookTrackingDictionary:
        return self._active_asks

    @property
    def active_bids(self) -> CryptoComOrderBookTrackingDictionary:
        return self._active_bids

    # TODO: research this more
    def volume_for_ask_price(self, price) -> float:
        return NotImplementedError

    # TODO: research this more
    def volume_for_bid_price(self, price) -> float:
        return NotImplementedError

    def get_rates_and_quantities(self, entry) -> tuple:
        # price, quantity
        return float(entry[0]), float(entry[1])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            list bid_entries = []
            list ask_entries = []
            str order_id
            str order_side
            str price_raw
            object price
            dict order_dict
            double timestamp = message.timestamp
            double amount = 0

        bid_entries = content["bids"]
        ask_entries = content["asks"]

        bids = s_empty_diff
        asks = s_empty_diff

        if len(bid_entries) > 0:
            bids = np.array(
                [[timestamp,
                  float(price),
                  float(amount),
                  message.update_id]
                 for price, amount in [self.get_rates_and_quantities(entry) for entry in bid_entries]],
                dtype="float64",
                ndmin=2
            )

        if len(ask_entries) > 0:
            asks = np.array(
                [[timestamp,
                  float(price),
                  float(amount),
                  message.update_id]
                 for price, amount in [self.get_rates_and_quantities(entry) for entry in ask_entries]],
                dtype="float64",
                ndmin=2
            )

        return bids, asks

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            float price
            float amount
            str order_id
            dict order_dict

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()
        timestamp = message.timestamp
        content = message.content

        for snapshot_orders, active_orders in [(content["bids"], self._active_bids), (content["asks"], self.active_asks)]:
            for order in snapshot_orders:
                price, amount = self.get_rates_and_quantities(order)

                order_dict = {
                    "order_id": timestamp,
                    "amount": amount
                }

                if price in active_orders:
                    active_orders[price][timestamp] = order_dict
                else:
                    active_orders[price] = {
                        timestamp: order_dict
                    }

        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [[message.timestamp,
                  price,
                  sum([order_dict["amount"]
                       for order_dict in self._active_bids[price].values()]),
                  message.update_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype="float64", ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  price,
                  sum([order_dict["amount"]
                       for order_dict in self.active_asks[price].values()]),
                  message.update_id]
                 for price in sorted(self.active_asks.keys(), reverse=True)], dtype="float64", ndmin=2
            )

        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

    cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message):
        cdef:
            double trade_type_value = 2.0

        timestamp = message.timestamp
        content = message.content

        return np.array(
            [timestamp, trade_type_value, float(content["price"]), float(content["size"])],
            dtype="float64"
        )

    def convert_diff_message_to_order_book_row(self, message):
        np_bids, np_asks = self.c_convert_diff_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row

    def convert_snapshot_message_to_order_book_row(self, message):
        np_bids, np_asks = self.c_convert_snapshot_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row
