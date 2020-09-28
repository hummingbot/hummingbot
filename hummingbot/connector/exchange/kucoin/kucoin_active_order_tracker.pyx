# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging

import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_kuaot_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")

KucoinOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]

cdef class KucoinActiveOrderTracker:
    def __init__(self,
                 active_asks: KucoinOrderBookTrackingDictionary = None,
                 active_bids: KucoinOrderBookTrackingDictionary = None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _kuaot_logger
        if _kuaot_logger is None:
            _kuaot_logger = logging.getLogger(__name__)
        return _kuaot_logger

    @property
    def active_asks(self) -> KucoinOrderBookTrackingDictionary:
        return self._active_asks

    @property
    def active_bids(self) -> KucoinOrderBookTrackingDictionary:
        return self._active_bids

    def volume_for_ask_price(self, price) -> float:
        return sum([float(msg["remaining_size"]) for msg in self._active_asks[price].values()])

    def volume_for_bid_price(self, price) -> float:
        return sum([float(msg["remaining_size"]) for msg in self._active_bids[price].values()])

    def get_rates_and_quantities(self, entry) -> tuple:
        return float(entry[0]), float(entry[1])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            list bid_entries = content["bids"]
            list ask_entries = content["asks"]
            str order_id
            str order_side
            str price_raw
            object price
            dict order_dict
            double timestamp = message.timestamp
            double quantity = 0

        bids = s_empty_diff
        asks = s_empty_diff

        if len(bid_entries) > 0:
            bids = np.array(
                [[timestamp,
                  float(price),
                  float(quantity),
                  message.update_id]
                 for price, quantity in [self.get_rates_and_quantities(entry) for entry in bid_entries]],
                dtype="float64",
                ndmin=2
            )

        if len(ask_entries) > 0:
            asks = np.array(
                [[timestamp,
                  float(price),
                  float(quantity),
                  message.update_id]
                 for price, quantity in [self.get_rates_and_quantities(entry) for entry in ask_entries]],
                dtype="float64",
                ndmin=2
            )

        return bids, asks

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            object price
            str order_id
            str amount
            dict order_dict

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()
        timestamp = message.timestamp

        for snapshot_orders, active_orders in [(message.content["bids"], self._active_bids), (message.content["asks"], self.active_asks)]:

            for order in snapshot_orders:
                price = order[0]
                amount = str(order[1])
                order_dict = {
                    "order_id": timestamp,
                    "quantity": amount
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
                  float(price),
                  sum([float(order_dict["quantity"])
                       for order_dict in self._active_bids[price].values()]),
                  message.update_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype="float64", ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  float(price),
                  sum([float(order_dict["quantity"])
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

        return np.array(
            [message.timestamp, trade_type_value, float(message.content["price"]), float(message.content["size"])],
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
