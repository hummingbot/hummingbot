# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging

import numpy as np
import math

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.connector.exchange.dydx.dydx_api_token_configuration_data_source import DydxAPITokenConfigurationDataSource
from hummingbot.connector.exchange.dydx.dydx_utils import hash_order_id

s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
_ddaot_logger = None

cdef class DydxActiveOrderTracker:
    def __init__(self, token_configuration, active_asks=None, active_bids=None):
        super().__init__()
        self._active_asks_by_price = active_asks or {}
        self._active_bids_by_price = active_bids or {}
        self._active_asks_by_id = {}
        self._active_bids_by_id = {}
        self._token_config: DydxAPITokenConfigurationDataSource = token_configuration

    @property
    def token_configuration(self) -> DydxAPITokenConfigurationDataSource:
        if not self._token_config:
            self._token_config = DydxAPITokenConfigurationDataSource.create()
        return self._token_config

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _ddaot_logger
        if _ddaot_logger is None:
            _ddaot_logger = logging.getLogger(__name__)
        return _ddaot_logger

    @property
    def active_asks_by_price(self):
        return self._active_asks_by_price

    @property
    def active_bids_by_price(self):
        return self._active_bids_by_price

    @property
    def active_asks_by_id(self):
        return self._active_asks_by_id

    @property
    def active_bids_by_id(self):
        return self._active_bids_by_id

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            object price
            str order_id

        # Refresh all order tracking.
        self._active_bids_by_price.clear()
        self._active_asks_by_price.clear()
        self._active_bids_by_id.clear()
        self._active_asks_by_id.clear()
        for bid_order in message.bids:
            price, amount = self.get_rates_and_quantities(float(bid_order["price"]), float(bid_order["amount"]), message.content["market"])
            level_id = hash_order_id(bid_order["id"])
            if price in self.active_bids_by_price:
                self.active_bids_by_price[price]["totalAmount"] += amount
                self.active_bids_by_price[price]["order_ids"].append(level_id)
            else:
                self.active_bids_by_price[price] = {
                    "totalAmount": amount,
                    "order_ids": [level_id]
                }
            self.active_bids_by_id[level_id] = {"price": price, "amount": amount}

        for ask_order in message.asks:
            price, amount = self.get_rates_and_quantities(float(ask_order["price"]), float(ask_order["amount"]), message.content["market"])
            level_id = hash_order_id(ask_order["id"])
            if price in self.active_asks_by_price:
                self.active_asks_by_price[price]["totalAmount"] += amount
                self.active_asks_by_price[price]["order_ids"].append(level_id)
            else:
                self.active_asks_by_price[price] = {
                    "totalAmount": amount,
                    "order_ids": [level_id]
                }
            self.active_asks_by_id[level_id] = {"price": price, "amount": amount}
        # Return the sorted snapshot tables.
        bids_list = []
        for price in sorted(self.active_bids_by_price.keys(), reverse=True):
            bids_list.append([message.timestamp,
                              float(price),
                              float(self.active_bids_by_price[price]["totalAmount"]),
                              self.active_bids_by_price[price]["order_ids"][0]])
        asks_list = []
        for price in sorted(self.active_asks_by_price.keys(), reverse=False):
            asks_list.append([message.timestamp,
                              float(price),
                              float(self.active_asks_by_price[price]["totalAmount"]),
                              self.active_asks_by_price[price]["order_ids"][0]])
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                bids_list, dtype="float64", ndmin=2)

            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                asks_list, dtype="float64", ndmin=2)

        # If there are no rows, the shape would become (1, 0) and not (0, 4).
        # Reshape to fix that.
        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))
        return bids, asks

    def get_rates_and_quantities(self, price, amount, market) -> tuple:
        pair_tuple = tuple(market.split('-'))
        basetokenid = self.token_configuration.get_tokenid(pair_tuple[0])
        quotetokenid = self.token_configuration.get_tokenid(pair_tuple[1])
        new_price = float(self.token_configuration.unpad_price(price, basetokenid, quotetokenid))
        new_amount = float(self.token_configuration.unpad(amount, basetokenid))
        return new_price, new_amount

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            str msg_type = content["type"]
            str market = content["market"]
            str order_id = content["id"]
            str order_side = content["side"]
            double timestamp = message.timestamp
            double quantity = 0

        bids = s_empty_diff
        asks = s_empty_diff
        correct_price = None

        level_id = hash_order_id(content["id"])
        if msg_type == "NEW":
            price = float(content["price"])
            amount = float(content["amount"])
            correct_price, preliminary_amount = self.get_rates_and_quantities(price, amount, market)
            if order_side == "BUY":
                self.active_bids_by_id[level_id] = {"price": correct_price, "amount": preliminary_amount}

                if correct_price in self.active_bids_by_price:
                    self.active_bids_by_price[correct_price]["totalAmount"] += preliminary_amount
                    correct_amount = self.active_bids_by_price[correct_price]["totalAmount"]
                    self.active_bids_by_price[correct_price]["order_ids"].append(level_id)
                else:
                    correct_amount = preliminary_amount
                    self.active_bids_by_price[correct_price] = {
                        "totalAmount": correct_amount,
                        "order_ids": [level_id]
                    }
            else:
                self.active_asks_by_id[level_id] = {"price": correct_price, "amount": preliminary_amount}

                if correct_price in self.active_asks_by_price:
                    self.active_asks_by_price[correct_price]["totalAmount"] += preliminary_amount
                    correct_amount = self.active_asks_by_price[correct_price]["totalAmount"]
                    self.active_asks_by_price[correct_price]["order_ids"].append(level_id)
                else:
                    correct_amount = preliminary_amount
                    self.active_asks_by_price[correct_price] = {
                        "totalAmount": correct_amount,
                        "order_ids": [level_id]
                    }
        elif msg_type in ["UPDATED", "REMOVED"]:
            if order_side == "BUY":
                try:
                    prev_order = self.active_bids_by_id[level_id]
                except KeyError:
                    self.logger().debug(f"Unrecognized order id for {msg_type} command")
                    raise KeyError
                correct_price = prev_order["price"]
                prev_order_list = self.active_bids_by_price[correct_price]
            else:
                try:
                    prev_order = self.active_asks_by_id[level_id]
                except KeyError:
                    self.logger().debug(f"Unrecognized order id for {msg_type} command")
                    raise KeyError
                correct_price = prev_order["price"]
                prev_order_list = self.active_asks_by_price[correct_price]
            if msg_type == "UPDATED":
                dummy_price, preliminary_amount = self.get_rates_and_quantities(correct_price, float(content["amount"]), market)
                prev_order_list["totalAmount"] = prev_order_list["totalAmount"] - prev_order["amount"] + preliminary_amount
                correct_amount = prev_order_list["totalAmount"]
                prev_order["amount"] = preliminary_amount
            else:
                dummy_price, preliminary_amount = self.get_rates_and_quantities(correct_price, float(0), market)
                if level_id in prev_order_list["order_ids"]:
                    new_total_amount = float(0)
                    for o_id in prev_order_list["order_ids"]:
                        if o_id == level_id:
                            continue
                        else:
                            if order_side == 'BUY':
                                new_total_amount += self.active_bids_by_id[o_id]["amount"]
                            else:
                                new_total_amount += self.active_asks_by_id[o_id]["amount"]
                    prev_order_list["totalAmount"] = new_total_amount
                    prev_order_list["order_ids"].remove(level_id)
                correct_amount = prev_order_list["totalAmount"]

        if correct_price is not None:
            if order_side == "BUY":
                bids = np.array(
                    [[timestamp,
                      float(correct_price),
                      float(correct_amount),
                      level_id]],
                    dtype="float64",
                    ndmin=2
                )

            elif order_side == "SELL":
                asks = np.array(
                    [[timestamp,
                      float(correct_price),
                      float(correct_amount),
                      level_id]],
                    dtype="float64",
                    ndmin=2
                )

        return bids, asks

    def convert_diff_message_to_order_book_row(self, message):
        np_bids, np_asks = self.c_convert_diff_message_to_np_arrays(message)
        bids_row = [ClientOrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [ClientOrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row

    def convert_snapshot_message_to_order_book_row(self, message):
        np_bids, np_asks = self.c_convert_snapshot_message_to_np_arrays(message)
        bids_row = [ClientOrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [ClientOrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row
