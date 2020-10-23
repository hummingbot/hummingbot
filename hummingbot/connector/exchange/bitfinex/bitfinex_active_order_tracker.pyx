# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging
import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_tracker_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")

TRACKING_DICT_TYPE = Dict[Decimal, Dict[str, Dict[str, any]]]

TYPE_OPEN = "open"
TYPE_CHANGE = "change"
TYPE_MATCH = "match"
TYPE_DONE = "done"
SIDE_BUY = "buy"
SIDE_SELL = "sell"


cdef class BitfinexActiveOrderTracker:

    def __init__(self,
                 active_asks: TRACKING_DICT_TYPE = None,
                 active_bids: TRACKING_DICT_TYPE = None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _tracker_logger
        if _tracker_logger is None:
            _tracker_logger = logging.getLogger(__name__)
        return _tracker_logger

    @property
    def active_asks(self) -> TRACKING_DICT_TYPE:
        """
        Get all asks on the order book in dictionary format
        :returns: Dict[price, Dict[order_id, order_book_message]]
        """
        return self._active_asks

    @property
    def active_bids(self) -> TRACKING_DICT_TYPE:
        """
        Get all bids on the order book in dictionary format
        :returns: Dict[price, Dict[order_id, order_book_message]]
        """
        return self._active_bids

    def volume_for_ask_price(self, price) -> float:
        """
        For a certain price, get the volume sum of all ask order book rows with that price
        :returns: volume sum
        """
        return sum([float(msg["remaining_size"]) for msg in self._active_asks[price].values()])

    def volume_for_bid_price(self, price) -> float:
        """
        For a certain price, get the volume sum of all bid order book rows with that price
        :returns: volume sum
        """
        return sum([float(msg["remaining_size"]) for msg in self._active_bids[price].values()])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            list bid_entries = content["bids"]
            list ask_entries = content["asks"]
            double order_id
            object price
            dict order_dict
            double timestamp = message.timestamp
            double quantity = 0

        bids = s_empty_diff
        asks = s_empty_diff

        if len(bid_entries) > 0:
            bids = np.array(
                [
                    [
                        float(timestamp),
                        float(price),
                        float(quantity),
                        float(message.update_id)
                    ]
                    for order_id, price, quantity in bid_entries
                ],
                dtype="float64",
                ndmin=2
            )

        if len(ask_entries) > 0:
            asks = np.array(
                [
                    [
                        float(timestamp),
                        float(price),
                        float(quantity),
                        float(message.update_id)
                    ]
                    for order_id, price, quantity in ask_entries
                ],
                dtype="float64",
                ndmin=2
            )

        return bids, asks

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        """
        Interpret an incoming snapshot message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """
        cdef:
            object price
            double order_id
            double amount
            dict order_dict

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()
        for snapshot_orders, active_orders in [(message.content.get("bids", 0), self._active_bids),
                                               (message.content.get("asks", 0), self._active_asks)]:
            for order in snapshot_orders:
                price = Decimal(order[0])
                order_id = order[2]
                amount = order[1]
                order_dict = {
                    "order_id": order_id,
                    "remaining_size": amount
                }

                if price in active_orders:
                    active_orders[price][order_id] = order_dict
                else:
                    active_orders[price] = {
                        order_id: order_dict
                    }

        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [
                    [
                        message.timestamp,
                        float(price),
                        sum(
                            [
                                float(order_dict["remaining_size"])
                                for order_dict in self._active_bids[price].values()
                            ]
                        ),
                        message.update_id
                    ]
                    for price in sorted(self._active_bids.keys(), reverse=True)
                ],
                dtype="float64",
                ndmin=2
            )
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [
                    [
                        message.timestamp,
                        float(price),
                        sum(
                            [
                                float(order_dict["remaining_size"])
                                for order_dict in self._active_asks[price].values()
                            ]
                        ),
                        message.update_id
                    ]
                    for price in sorted(self._active_asks.keys(), reverse=True)
                ],
                dtype="float64",
                ndmin=2
            )

        # If there're no rows, the shape would become (1, 0) and not (0, 4).
        # Reshape to fix that.
        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

    cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message):
        """
        Interpret an incoming trade message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple[np.array (bids), np.array (asks)]
        """
        cdef:
            double trade_type_value = 1.0 if message.content["side"] == SIDE_SELL else 2.0

        return np.array(
            [
                message.timestamp,
                trade_type_value,
                float(message.content["price"]),
                float(message.content["size"])
            ],
            dtype="float64"
        )

    def convert_snapshot_message_to_order_book_row(self, message):
        """
        Convert an incoming snapshot message to Tuple of np.arrays, and then convert to OrderBookRow
        :returns: Tuple(List[bids_row], List[asks_row])
        """
        np_bids, np_asks = self.c_convert_snapshot_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row

    def convert_diff_message_to_order_book_row(self, message):
        """
        Convert an incoming diff message to Tuple of np.arrays, and then convert to OrderBookRow
        :returns: Tuple(List[bids_row], List[asks_row])
        """
        np_bids, np_asks = self.c_convert_diff_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row
