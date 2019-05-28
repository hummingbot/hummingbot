# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging

import numpy as np
from decimal import Decimal

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
_ddaot_logger = None

cdef class DDEXActiveOrderTracker:
    def __init__(self, active_asks=None, active_bids=None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _ddaot_logger
        if _ddaot_logger is None:
            _ddaot_logger = logging.getLogger(__name__)
        return _ddaot_logger

    @property
    def active_asks(self):
        return self._active_asks

    @property
    def active_bids(self):
        return self._active_bids

    def volume_for_ask_price(self, price):
        return sum([float(msg["availableAmount"]) for msg in self._active_asks[price].values()])

    def volume_for_bid_price(self, price):
        return sum([float(msg["availableAmount"]) for msg in self._active_bids[price].values()])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        # Look at the diff message type - it can be "receive" or "done".
        cdef:
            str message_type = message.content["type"]
            object price = Decimal(message.content["price"])
            double timestamp = message.timestamp
            double quantity = 0
            str order_type = message.content["orderType"]

        # Only process limit orders
        if order_type != "limit":
            return s_empty_diff, s_empty_diff
        # If it is "trade_success", it means an existing order is either completely or partially filled, and we need to
        # update or remove the order
        if message_type == "trade_success":
            side = message.content["makerSide"]
            order_id = message.content["makerOrderId"]
            if side == "buy":
                if price in self._active_bids and order_id in self._active_bids[price]:
                    self._active_bids[price][order_id]["availableAmount"] -= float(message.content["amount"])
                    if self._active_bids[price][order_id]["availableAmount"] == 0:
                        del self._active_bids[price][order_id]

                    if len(self._active_bids[price]) < 1:
                        del self._active_bids[price]
                        return (np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64"),
                                s_empty_diff)
                    else:
                        quantity = self.volume_for_bid_price(price)
                        return np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"), \
                               s_empty_diff
                else:
                    self.logger().info(f"Order not found in active bids: {message.content}. {price in self._active_bids}")

            elif side == "sell":
                if price in self._active_asks and order_id in self._active_asks[price]:
                    self._active_asks[price][order_id]["availableAmount"] -= float(message.content["amount"])
                    if self._active_asks[price][order_id]["availableAmount"] == 0:
                        del self._active_asks[price][order_id]

                    if len(self._active_asks[price]) < 1:
                        del self._active_asks[price]
                        return (s_empty_diff,
                                np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64"))
                    else:
                        quantity = self.volume_for_ask_price(price)
                        return s_empty_diff, \
                               np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64")
                else:
                    self.logger().info(f"Order not found in active asks: {message.content}. {price in self._active_bids}")

            return s_empty_diff, s_empty_diff
        # If it is "receive", it means a new order is opened. Start tracking it and output a diff row on the respective
        # order book.
        if message_type == "receive":
            side = message.content["side"]
            order_id = message.content["orderId"]
            message.content["availableAmount"] = float(message.content["availableAmount"])
            if side == "buy":
                if price in self._active_bids:
                    self._active_bids[price][order_id] = message.content
                else:
                    self._active_bids[price] = {order_id: message.content}

                quantity = self.volume_for_bid_price(price)
                return np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"), s_empty_diff
            elif side == "sell":
                if price in self._active_asks:
                    self._active_asks[price][order_id] = message.content
                else:
                    self._active_asks[price] = {order_id: message.content}

                quantity = self.volume_for_ask_price(price)
                return s_empty_diff, np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64")
            else:
                raise ValueError(f"Unknown order side '{side}'. Aborting.")

        # If it is "done", it means an order is removed. Remove it from tracking and output a diff row on the respective
        # order book.
        elif message_type == "done":
            side = message.content["side"]
            order_id = message.content["orderId"]
            message.content["availableAmount"] = float(message.content["availableAmount"])
            if side == "buy":
                if price in self._active_bids:
                    if order_id in self._active_bids[price]:
                        del self._active_bids[price][order_id]
                    else:
                        self.logger().info(f"Order not found in active bids: {message.content}.")

                    if len(self._active_bids[price]) < 1:
                        del self._active_bids[price]
                        return (np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64"),
                                s_empty_diff)
                    else:
                        quantity = self.volume_for_bid_price(price)
                        return (np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"),
                                s_empty_diff)
                else:
                    return s_empty_diff, s_empty_diff
            elif side == "sell":
                if price in self._active_asks:
                    if order_id in self._active_asks[price]:
                        del self._active_asks[price][order_id]
                    else:
                        self.logger().info(f"Order not found in active asks: {message.content}.")

                    if len(self._active_asks[price]) < 1:
                        del self._active_asks[price]
                        return (s_empty_diff,
                                np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64"))
                    else:
                        quantity = self.volume_for_ask_price(price)
                        return (s_empty_diff,
                                np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"))
                else:
                    return s_empty_diff, s_empty_diff
            else:
                raise ValueError(f"Unknown order side '{side}'. Aborting.")
        elif message_type in ["open", "change", "level3OrderbookSnapshot"]:
            # These messages are not used for tracking order book
            return s_empty_diff, s_empty_diff
        else:
            raise ValueError(f"Unknown message type '{message_type}'. Must be 'trade_success', 'receive', 'change', "
                             f"'level3OrderbookSnapshot' or 'done'.")

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            object price
            str order_id
            str amount

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()

        for bid_order in message.content["bids"]:
            price = Decimal(bid_order["price"])
            order_id = bid_order["orderId"]
            amount = bid_order["amount"]
            order_dict = {
                "availableAmount": float(amount),
                "orderId": order_id
            }

            if price in self._active_bids:
                self._active_bids[price][order_id] = order_dict
            else:
                self._active_bids[price] = {
                    order_id: order_dict
                }

        for ask_order in message.content["asks"]:
            price = Decimal(ask_order["price"])
            order_id = ask_order["orderId"]
            amount = ask_order["amount"]
            order_dict = {
                "availableAmount": float(amount),
                "orderId": order_id
            }

            if price in self._active_asks:
                self._active_asks[price][order_id] = order_dict
            else:
                self._active_asks[price] = {
                    order_id: order_dict
                }

        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [[message.timestamp,
                  float(price),
                  sum([float(order_dict["availableAmount"])
                       for order_dict in self._active_bids[price].values()]),
                  message.update_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype="float64", ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  float(price),
                  sum([float(order_dict["availableAmount"])
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
        cdef:
            str maker_order_id = message.content["makerOrderId"]
            str taker_order_id = message.content["takerOrderId"]
            object price = Decimal(message.content["price"])
            double trade_type_value = 1.0 if message.content["makerSide"] == "sell" else 2.0

        return np.array([message.timestamp, trade_type_value, float(price), float(message.content["amount"])],
                        dtype="float64")

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
