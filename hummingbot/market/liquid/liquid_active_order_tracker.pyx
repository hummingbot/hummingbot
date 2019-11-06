# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging
import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

LiquidOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]


cdef class LiquidActiveOrderTracker:
    def __init__(self,
                active_asks: LiquidOrderBookTrackingDictionary = None,
                active_bids: LiquidOrderBookTrackingDictionary = None):
        super().__init__()

        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _cbpaot_logger
        if _cbpaot_logger is None:
            _cbpaot_logger = logging.getLogger(__name__)
        return _cbpaot_logger

    @property
    def active_asks(self) -> LiquidOrderBookTrackingDictionary:
        """
        Get all asks on the order book in dictionary format
        :returns: Dict[price, Dict[order_id, order_book_message]]
        """
        return self._active_asks

    @property
    def active_bids(self) -> LiquidOrderBookTrackingDictionary:
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

    def convert_snapshot_message_to_order_book_row(self, message):
        """
        Convert an incoming snapshot message to Tuple of np.arrays, and then convert to OrderBookRow
        :returns: Tuple(List[bids_row], List[asks_row])
        """
        np_bids, np_asks = self.c_convert_snapshot_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        """
        Interpret an incoming snapshot message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """
        cdef:
            object price
            str order_id
            str amount
            dict order_dict

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()

        timestamp = message.timestamp

        for snapshot_orders, active_orders in [(message.content["buy_price_levels"], self._active_bids),
                                               (message.content["sell_price_levels"], self._active_asks)]:

            for order in snapshot_orders:
                price = Decimal(order[0])
                amount = order[1]

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

        # Return the sorted snapshot tables.
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
                       for order_dict in self._active_asks[price].values()]),
                  message.update_id]
                 for price in sorted(self._active_asks.keys(), reverse=True)], dtype="float64", ndmin=2)

        # If there're no rows, the shape would become (1, 0) and not (0, 4).
        # Reshape to fix that.
        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks
