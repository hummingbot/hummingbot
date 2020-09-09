# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging
import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_cbpaot_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")

CoinbaseProOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]

TYPE_OPEN = "open"
TYPE_CHANGE = "change"
TYPE_MATCH = "match"
TYPE_DONE = "done"
SIDE_BUY = "buy"
SIDE_SELL = "sell"

cdef class CoinbaseProActiveOrderTracker:
    def __init__(self,
                 active_asks: CoinbaseProOrderBookTrackingDictionary = None,
                 active_bids: CoinbaseProOrderBookTrackingDictionary = None):
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
    def active_asks(self) -> CoinbaseProOrderBookTrackingDictionary:
        """
        Get all asks on the order book in dictionary format
        :returns: Dict[price, Dict[order_id, order_book_message]]
        """
        return self._active_asks

    @property
    def active_bids(self) -> CoinbaseProOrderBookTrackingDictionary:
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
        """
        Interpret an incoming diff message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """

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

        order_id = content.get("order_id") or content.get("maker_order_id")
        order_side = content.get("side")
        price_raw = content.get("price")
        if order_id is None:
            raise ValueError(f"Unknown order id for message - '{message}'. Aborting.")
        if order_side not in [SIDE_BUY, SIDE_SELL]:
            raise ValueError(f"Unknown order side for message - '{message}'. Aborting.")
        if price_raw is None:
            raise ValueError(f"Unknown order price for message - '{message}'. Aborting.")
        elif price_raw == "null":  # 'change' messages have 'null' as price for market orders
            return s_empty_diff, s_empty_diff
        price = Decimal(price_raw)

        if msg_type == TYPE_OPEN:
            order_dict = {
                "order_id": order_id,
                "remaining_size": content["remaining_size"]
            }
            if order_side == SIDE_BUY:
                if price in self._active_bids:
                    self._active_bids[price][order_id] = order_dict
                else:
                    self._active_bids[price] = {order_id: order_dict}
                quantity = self.volume_for_bid_price(price)
                return np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"), s_empty_diff
            else:
                if price in self._active_asks:
                    self._active_asks[price][order_id] = order_dict
                else:
                    self._active_asks[price] = {order_id: order_dict}
                quantity = self.volume_for_ask_price(price)
                return s_empty_diff, np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64")

        elif msg_type == TYPE_CHANGE:
            if content.get("new_size") is not None:
                remaining_size = content["new_size"]
            elif content.get("new_funds") is not None:
                remaining_size = str(Decimal(content["new_funds"]) / price)
            else:
                raise ValueError(f"Invalid change message - '{message}'. Aborting.")
            if order_side == SIDE_BUY:
                if price in self._active_bids and order_id in self._active_bids[price]:
                    self._active_bids[price][order_id]["remaining_size"] = remaining_size
                    quantity = self.volume_for_bid_price(price)
                    return (
                        np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"),
                        s_empty_diff
                    )
                else:
                    return s_empty_diff, s_empty_diff
            else:
                if price in self._active_asks and order_id in self._active_asks[price]:
                    self._active_asks[price][order_id]["remaining_size"] = remaining_size
                    quantity = self.volume_for_ask_price(price)
                    return (
                        s_empty_diff,
                        np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64")
                    )
                else:
                    return s_empty_diff, s_empty_diff

        elif msg_type == TYPE_MATCH:
            if order_side == SIDE_BUY:
                if price in self._active_bids and order_id in self._active_bids[price]:
                    remaining_size = self._active_bids[price][order_id]["remaining_size"]
                    self._active_bids[price][order_id]["remaining_size"] = str(float(remaining_size) - float(content["size"]))
                    quantity = self.volume_for_bid_price(price)
                    return (
                        np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"),
                        s_empty_diff
                    )
                else:
                    return s_empty_diff, s_empty_diff
            else:
                if price in self._active_asks and order_id in self._active_asks[price]:
                    remaining_size = self._active_asks[price][order_id]["remaining_size"]
                    self._active_asks[price][order_id]["remaining_size"] = str(float(remaining_size) - float(content["size"]))
                    quantity = self.volume_for_ask_price(price)
                    return (
                        s_empty_diff,
                        np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64")
                    )
                else:
                    return s_empty_diff, s_empty_diff

        elif msg_type == TYPE_DONE:
            if order_side == SIDE_BUY:
                if price in self._active_bids and order_id in self._active_bids[price]:
                    del self._active_bids[price][order_id]
                    if len(self._active_bids[price]) < 1:
                        del self._active_bids[price]
                        return (
                            np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64"),
                            s_empty_diff
                        )
                    else:
                        quantity = self.volume_for_bid_price(price)
                        return (
                            np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"),
                            s_empty_diff
                        )
                return s_empty_diff, s_empty_diff
            else:
                if price in self._active_asks and order_id in self._active_asks[price]:
                    del self._active_asks[price][order_id]
                    if len(self._active_asks[price]) < 1:
                        del self._active_asks[price]
                        return (
                            s_empty_diff,
                            np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64")
                        )
                    else:
                        quantity = self.volume_for_ask_price(price)
                        return (
                            s_empty_diff,
                            np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64")
                        )
                return s_empty_diff, s_empty_diff

        else:
            raise ValueError(f"Unknown message type '{msg_type}' - {message}. Aborting.")

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
        for snapshot_orders, active_orders in [(message.content["bids"], self._active_bids),
                                               (message.content["asks"], self._active_asks)]:
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
                [[message.timestamp,
                  float(price),
                  sum([float(order_dict["remaining_size"])
                       for order_dict in self._active_bids[price].values()]),
                  message.update_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype="float64", ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  float(price),
                  sum([float(order_dict["remaining_size"])
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
