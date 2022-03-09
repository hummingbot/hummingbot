import logging
from decimal import Decimal
from typing import Dict

import numpy as np

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.logger import HummingbotLogger

_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
AscendExOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]


class AscendExActiveOrderTracker:
    def __init__(self,
                 active_asks: AscendExOrderBookTrackingDictionary = None,
                 active_bids: AscendExOrderBookTrackingDictionary = None):
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
    def active_asks(self) -> AscendExOrderBookTrackingDictionary:
        return self._active_asks

    @property
    def active_bids(self) -> AscendExOrderBookTrackingDictionary:
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

    def convert_diff_message_to_np_arrays(self, message: object) -> tuple:
        bid_entries = message.content["bids"]
        ask_entries = message.content["asks"]

        bids = s_empty_diff
        asks = s_empty_diff

        if len(bid_entries) > 0:
            bids = np.array(
                [[message.timestamp,
                  float(price),
                  float(amount),
                  message.update_id]
                 for price, amount in [self.get_rates_and_quantities(entry) for entry in bid_entries]],
                dtype="float64",
                ndmin=2
            )

        if len(ask_entries) > 0:
            asks = np.array(
                [[message.timestamp,
                  float(price),
                  float(amount),
                  message.update_id]
                 for price, amount in [self.get_rates_and_quantities(entry) for entry in ask_entries]],
                dtype="float64",
                ndmin=2
            )

        return bids, asks

    def convert_snapshot_message_to_np_arrays(self, message: object) -> tuple:
        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()
        timestamp = message.timestamp
        content = message.content

        for snapshot_orders, active_orders in [(content["bids"], self._active_bids),
                                               (content["asks"], self.active_asks)]:
            for order in snapshot_orders:
                price, amount = self.get_rates_and_quantities(order)

                order_dict = {
                    "order_id": timestamp,
                    "amount": amount
                }

                if price in active_orders:
                    active_orders[price][timestamp] = order_dict
                else:
                    active_orders[price] = {
                        timestamp: order_dict
                    }

        bids = np.array(
            [[message.timestamp,
              price,
              sum([order_dict["amount"]
                   for order_dict in self._active_bids[price].values()]),
              message.update_id]
             for price in sorted(self._active_bids.keys(), reverse=True)], dtype="float64", ndmin=2)
        asks = np.array(
            [[message.timestamp,
              price,
              sum([order_dict["amount"]
                   for order_dict in self.active_asks[price].values()]),
              message.update_id]
             for price in sorted(self.active_asks.keys(), reverse=True)], dtype="float64", ndmin=2
        )

        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

    def convert_trade_message_to_np_array(self, message: object) -> np.ndarray:
        trade_type_value = 2.0

        timestamp = message.timestamp
        content = message.content

        return np.array(
            [timestamp, trade_type_value, float(content["price"]), float(content["size"])],
            dtype="float64"
        )

    def convert_diff_message_to_order_book_row(self, message):
        np_bids, np_asks = self.convert_diff_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row

    def convert_snapshot_message_to_order_book_row(self, message):
        np_bids, np_asks = self.convert_snapshot_message_to_np_arrays(message)
        bids_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_bids]
        asks_row = [OrderBookRow(price, qty, update_id) for ts, price, qty, update_id in np_asks]
        return bids_row, asks_row
