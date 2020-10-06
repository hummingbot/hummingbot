# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging
import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_rraot_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")

RadarRelayOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]


cdef class RadarRelayActiveOrderTracker:
    def __init__(self,
                 active_asks: RadarRelayOrderBookTrackingDictionary = None,
                 active_bids: RadarRelayOrderBookTrackingDictionary = None,
                 order_price_map: Dict[str, Decimal] = None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}
        self._order_price_map = order_price_map or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _rraot_logger
        if _rraot_logger is None:
            _rraot_logger = logging.getLogger(__name__)
        return _rraot_logger

    @property
    def active_asks(self) -> RadarRelayOrderBookTrackingDictionary:
        return self._active_asks

    @property
    def active_bids(self) -> RadarRelayOrderBookTrackingDictionary:
        return self._active_bids

    @property
    def order_price_map(self) -> Dict[str, Decimal]:
        return self._order_price_map

    def volume_for_ask_price(self, price) -> float:
        return sum([float(msg["remainingBaseTokenAmount"]) for msg in self._active_asks[price].values()])

    def volume_for_bid_price(self, price) -> float:
        return sum([float(msg["remainingBaseTokenAmount"]) for msg in self._active_bids[price].values()])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        # "CANCEL" and "REMOVE" messages contain only orderHash and not price which is why "_order_price_map" is
        # required.
        cdef:
            str action = message.content["action"]
            dict event = message.content["event"]
            str order_side
            str order_hash
            object price
            double timestamp = message.timestamp
            double quantity = 0

        if action == "NEW":
            order_side = event["order"]["type"]
            order_hash = event["order"]["orderHash"]
            price = Decimal(event["order"]["price"])
            self._order_price_map[order_hash] = price
            order_dict = {
                "orderHash": order_hash,
                "remainingBaseTokenAmount": event["order"]["remainingBaseTokenAmount"]
            }
            if order_side == "BID":
                if price in self._active_bids:
                    self._active_bids[price][order_hash] = order_dict
                else:
                    self._active_bids[price] = {order_hash: order_dict}

                quantity = self.volume_for_bid_price(price)
                return np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"), s_empty_diff

            elif order_side == "ASK":
                if price in self._active_asks:
                    self._active_asks[price][order_hash] = order_dict
                else:
                    self._active_asks[price] = {order_hash: order_dict}

                quantity = self.volume_for_ask_price(price)
                return s_empty_diff, np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64")
            else:
                raise ValueError(f"Unknown order side '{order_side}'. Aborting.")

        elif action in ["REMOVE", "CANCEL"]:
            order_side = event["orderType"]
            order_hash = event["orderHash"]
            if order_hash in self._order_price_map:
                price = self._order_price_map[order_hash]
            else:
                self.logger().debug(f"OrderHash {order_hash} {message.timestamp} order not found in order price map")
                return s_empty_diff, s_empty_diff

            del self._order_price_map[order_hash]

            if order_side == "BID":
                if price in self._active_bids:
                    if order_hash in self._active_bids[price]:
                        del self._active_bids[price][order_hash]

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
            elif order_side == "ASK":
                if price in self._active_asks:
                    if order_hash in self._active_asks[price]:
                        del self._active_asks[price][order_hash]

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
                raise ValueError(f"Unknown order side '{order_side}'. Aborting.")

        elif action == "FILL":
            remaining_base_amount = Decimal(event["order"]["remainingBaseTokenAmount"])
            order_hash = event["order"]["orderHash"]
            price = Decimal(event["order"]["price"])
            order_side = event["type"]
            if order_side == "BUY":
                if price in self._active_bids:
                    if order_hash in self._active_bids[price]:
                        if event["order"]["state"] == "FILLED":
                            del self._order_price_map[order_hash]
                            del self._active_bids[price][order_hash]
                        else:  # update the remaining amount of the order
                            self._active_bids[price][order_hash]["remainingBaseTokenAmount"] = remaining_base_amount

                        if len(self._active_bids[price]) < 1:
                            del self._active_bids[price]
                            return (np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64"),
                                    s_empty_diff)
                        else:
                            quantity = self.volume_for_bid_price(price)
                            return (np.array([[timestamp, float(price), quantity, message.update_id]], dtype="float64"),
                                    s_empty_diff)

                # return empty diff if order or price is not found
                return s_empty_diff, s_empty_diff
            elif order_side == "SELL":
                if price in self._active_asks:
                    if order_hash in self._active_asks[price]:
                        if event["order"]["state"] == "FILLED":
                            del self._order_price_map[order_hash]
                            del self._active_asks[price][order_hash]
                        else:  # update the remaining amount of the order
                            self._active_asks[price][order_hash]["remainingBaseTokenAmount"] = remaining_base_amount

                        if len(self._active_asks[price]) < 1:
                            del self._active_asks[price]
                            return (s_empty_diff,
                                    np.array([[timestamp, float(price), 0.0, message.update_id]], dtype="float64"))
                        else:
                            quantity = self.volume_for_ask_price(price)
                            return (s_empty_diff,
                                    np.array([[timestamp, float(price), quantity, message.update_id]],
                                             dtype="float64"))

                # return empty diff if order or price is not found
                return s_empty_diff, s_empty_diff

        else:
            raise ValueError(f"Unknown action type '{action}'. Must be 'NEW', 'REMOVE', 'CANCEL' or 'FILL'.")

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            object price
            str order_hash
            str amount

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()
        self._order_price_map.clear()
        for snapshot_orders, active_orders in [(message.content["bids"], self._active_bids),
                                               (message.content["asks"], self._active_asks)]:
            for order in snapshot_orders:
                price = Decimal(order["price"])
                order_hash = order["orderHash"]
                order_dict = {
                    "orderHash": order_hash,
                    "remainingBaseTokenAmount": order["remainingBaseTokenAmount"]
                }

                if price in active_orders:
                    active_orders[price][order_hash] = order_dict
                else:
                    active_orders[price] = {
                        order_hash: order_dict
                    }
                self._order_price_map[order_hash] = price

        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [[message.timestamp,
                  float(price),
                  sum([float(order_dict["remainingBaseTokenAmount"])
                       for order_dict in self._active_bids[price].values()]),
                  message.update_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype="float64", ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  float(price),
                  sum([float(order_dict["remainingBaseTokenAmount"])
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
            str order_id = message.content["event"]["order"]["orderHash"]
            object price = Decimal(message.content["event"]["order"]["price"])
            double trade_type_value = 1.0 if message.content["event"]["type"] == "ASK" else 2.0
            double filled_base_amount = Decimal(message.content["event"]["filledBaseTokenAmount"])

        return np.array([message.timestamp, trade_type_value, float(price), float(filled_base_amount)],
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
