# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging
import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow
import hummingbot.connector.exchange.coinex.coinex_constants as Constants

_cbpaot_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")

CoinexOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]

# TODO: Move to constants
TYPE_OPEN = "open"
TYPE_CHANGE = "change"
TYPE_MATCH = "match"
TYPE_DONE = "done"
SIDE_BUY = "buy"
SIDE_SELL = "sell"

cdef class CoinexActiveOrderTracker:
    def __init__(self,
                 active_asks: CoinexOrderBookTrackingDictionary = None,
                 active_bids: CoinexOrderBookTrackingDictionary = None):
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
    def active_asks(self) -> CoinexOrderBookTrackingDictionary:
        """
        Get all asks on the order book in dictionary format
        :returns: Dict[price, Dict[order_id, order_book_message]]
        """
        return self._active_asks

    @property
    def active_bids(self) -> CoinexOrderBookTrackingDictionary:
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

    def get_rates_and_quantities(self, entry) -> tuple:
        return float(entry[0]), float(entry[1])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        """
        Interpret an incoming diff message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """
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

        for snapshot_orders, active_orders in [(message.content["bids"], self._active_bids),
                                               (message.content["asks"], self._active_asks)]:
            for order in snapshot_orders:
                price = Decimal(order[0])
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

    cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message):
        """
        Interpret an incoming trade message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple[np.array (bids), np.array (asks)]
        """
        cdef:
            double trade_type_value = 1.0 if message.content["side"] == SIDE_SELL else 2.0

        return np.array(
            [message.timestamp, trade_type_value, float(message.content["price"]), float(message.content["size"])],
            dtype="float64"
        )

    def convert_diff_message_to_order_book_row(self, message):
        """
        Convert an incoming diff message to Tuple of np.arrays, and then convert to OrderBookRow
        :returns: Tuple(List[bids_row], List[asks_row])
        TODO: What do we do if there are no asks?
        """
        np_bids, np_asks = self.c_convert_diff_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row

    def convert_snapshot_message_to_order_book_row(self, message):
        """
        Convert an incoming snapshot message to Tuple of np.arrays, and then convert to OrderBookRow
        :returns: Tuple(List[bids_row], List[asks_row])
        """
        np_bids, np_asks = self.c_convert_snapshot_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row
