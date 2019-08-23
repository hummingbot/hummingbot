# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging

import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_btaot_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")

BittrexOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]

TYPE_OPEN = "open"
TYPE_CHANGE = "change"
TYPE_MATCH = "match"
TYPE_DONE = "done"
SIDE_BUY = "buy"
SIDE_SELL = "sell"

cdef class BittrexActiveOrderTracker:
    def __init__(self,
                 active_asks: BittrexOrderBookTrackingDictionary = None,
                 active_bids: BittrexOrderBookTrackingDictionary = None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _btaot_logger
        if _btaot_logger is None:
            _btaot_logger = logging.getLogger(__name__)
        return _btaot_logger

    @property
    def active_asks(self) -> BittrexOrderBookTrackingDictionary:
        return self._active_asks

    @property
    def active_bids(self) -> BittrexOrderBookTrackingDictionary:
        return self._active_bids

    def volume_for_ask_price(self, price) -> float:
        return sum([float(msg["remaining_size"]) for msg in self._active_asks[price].values()])

    def volume_for_bid_price(self, price) -> float:
        return sum([float(msg["remaining_size"]) for msg in self._active_bids[price].values()])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            str msg_type = content["type"]
            str order_id
            str order_side
            str price_raw
            object price
            dict order_dict
            str remaining_size
            double timestamp = message.timestamp
            double quantity = 0

        bids = {}
        asks = {}
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

        bids = {}
        asks = {}

        return bids, asks

    cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message):
        cdef:
            double trade_type_value = 1.0 if message.content["side"] == SIDE_SELL else 2.0

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
