# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp
import logging
from decimal import Decimal
from typing import Dict

import numpy as np
from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.logger import HummingbotLogger

_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
GateIoOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]

cdef class GateIoActiveOrderTracker:
    def __init__(self,
                 active_asks: GateIoOrderBookTrackingDictionary = None,
                 active_bids: GateIoOrderBookTrackingDictionary = None):
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
    def active_asks(self) -> GateIoOrderBookTrackingDictionary:
        return self._active_asks

    @property
    def active_bids(self) -> GateIoOrderBookTrackingDictionary:
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

    # def get_rates_and_quantities_alt(self, entry) -> tuple:
    #     # price, quantity
    #     return float(entry["p"]), float(entry["s"])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            list content_keys = list(content.keys())
            list bid_entries = []
            list ask_entries = []
            str order_id
            str order_side
            str price_raw
            object price
            dict order_dict
            double timestamp = message.timestamp
            double amount = 0

        if "b" in content_keys:
            bid_entries = content["b"]
        if "a" in content_keys:
            ask_entries = content["a"]

        bids = s_empty_diff
        asks = s_empty_diff

        if len(bid_entries) > 0:
            bids = np.array(
                [[timestamp,
                  price,
                  amount,
                  message.update_id]
                 for price, amount in [self.get_rates_and_quantities(entry) for entry in bid_entries]],
                dtype="float64",
                ndmin=2
            )

        if len(ask_entries) > 0:
            asks = np.array(
                [[timestamp,
                  price,
                  amount,
                  message.update_id]
                 for price, amount in [self.get_rates_and_quantities(entry) for entry in ask_entries]],
                dtype="float64",
                ndmin=2
            )

        return bids, asks

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            object price
            double amount
            str order_id
            dict order_dict

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()
        timestamp = message.timestamp
        content = message.content

        for snapshot_orders, active_orders in [(content["bids"], self._active_bids), (content["asks"], self._active_asks)]:
            for entry in snapshot_orders:
                price, amount = self.get_rates_and_quantities(entry)
                active_orders[price] = amount

        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [[message.timestamp,
                  float(price),
                  float(self._active_bids[price]),
                  message.update_id]
                 for price in sorted(self._active_bids.keys())], dtype='float64', ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  float(price),
                  float(self._active_asks[price]),
                  message.update_id]
                 for price in sorted(self._active_asks.keys(), reverse=True)], dtype='float64', ndmin=2)

        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

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
