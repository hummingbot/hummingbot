# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging

import numpy as np
import math
from decimal import Decimal

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import ClientOrderBookRow
from hummingbot.connector.exchange.loopring.loopring_api_token_configuration_data_source import LoopringAPITokenConfigurationDataSource

s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
_ddaot_logger = None

cdef class LoopringActiveOrderTracker:
    def __init__(self, token_configuration, active_asks=None, active_bids=None):
        super().__init__()
        self._token_config: LoopringAPITokenConfigurationDataSource = token_configuration
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

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            object price
            str order_id

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()

        for bid_order in message.bids:
            order_id = str(message.timestamp)
            price, totalAmount = self.get_rates_and_quantities(bid_order, message.content["topic"]["market"])
            order_dict = {
                "availableAmount": Decimal(totalAmount),
                "orderId": order_id
            }
            if price in self._active_bids:
                self._active_bids[price][order_id] = order_dict
            else:
                self._active_bids[price] = {
                    order_id: order_dict
                }

        for ask_order in message.asks:
            price = Decimal(ask_order[0])
            order_id = str(message.timestamp)
            price, totalAmount = self.get_rates_and_quantities(ask_order, message.content["topic"]["market"])
            order_dict = {
                "availableAmount": Decimal(totalAmount),
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
                  Decimal(price),
                  sum([Decimal(order_dict["availableAmount"])
                       for order_dict in self._active_bids[price].values()]),
                  order_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype="float64", ndmin=2)

            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  Decimal(price),
                  sum([Decimal(order_dict["availableAmount"])
                       for order_dict in self._active_asks[price].values()]),
                  order_id]
                 for price in sorted(self._active_asks.keys(), reverse=True)], dtype="float64", ndmin=2)

        # If there're no rows, the shape would become (1, 0) and not (0, 4).
        # Reshape to fix that.
        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))
        return bids, asks

    def get_rates_and_quantities(self, entry, market) -> tuple:
        pair_tuple = tuple(market.split('-'))
        tokenid = self._token_config.get_tokenid(pair_tuple[0])
        return float(entry[0]), float(self._token_config.unpad(entry[1], tokenid))

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            list bid_entries = content["data"]["bids"]
            list ask_entries = content["data"]["asks"]
            str market = content["topic"]["market"]
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
                  message.content["endVersion"]]
                 for price, quantity in [self.get_rates_and_quantities(entry, market) for entry in bid_entries]],
                dtype="float64",
                ndmin=2
            )

        if len(ask_entries) > 0:
            asks = np.array(
                [[timestamp,
                  float(price),
                  float(quantity),
                  message.content["endVersion"]]
                 for price, quantity in [self.get_rates_and_quantities(entry, market) for entry in ask_entries]],
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
