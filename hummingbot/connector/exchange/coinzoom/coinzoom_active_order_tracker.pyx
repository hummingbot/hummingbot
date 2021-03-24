# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp
import logging
import numpy as np
from decimal import Decimal
from typing import Dict
from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype="float64")
CoinzoomOrderBookTrackingDictionary = Dict[Decimal, Dict[str, Dict[str, any]]]

cdef class CoinzoomActiveOrderTracker:
    def __init__(self,
                 active_asks: CoinzoomOrderBookTrackingDictionary = None,
                 active_bids: CoinzoomOrderBookTrackingDictionary = None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}
        self._active_asks_ids = {}
        self._active_bids_ids = {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _logger
        if _logger is None:
            _logger = logging.getLogger(__name__)
        return _logger

    @property
    def active_asks(self) -> CoinzoomOrderBookTrackingDictionary:
        return self._active_asks

    @property
    def active_bids(self) -> CoinzoomOrderBookTrackingDictionary:
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

    def get_rates_and_amts_with_ids(self, entry, id_list) -> tuple:
        if len(entry) > 1:
            price = float(entry[1])
            amount = float(entry[2])
            id_list[str(entry[0])] = price
        else:
            price = id_list.get(str(entry[0]))
            amount = 0.0
        return price, amount

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        cdef:
            dict content = message.content
            list content_keys = list(content.keys())
            list bid_entries = []
            list ask_entries = []
            str order_id
            str order_side
            str price_raw
            object price
            dict order_dict
            double timestamp = message.timestamp
            double amount = 0
            dict nps = {'bids': s_empty_diff, 'asks': s_empty_diff}

        if "b" in content_keys:
            bid_entries = content["b"]
        if "s" in content_keys:
            ask_entries = content["s"]

        for entries, diff_key, id_list in [
            (bid_entries, 'bids', self._active_bids_ids),
            (ask_entries, 'asks', self._active_asks_ids)
        ]:
            if len(entries) > 0:
                nps[diff_key] = np.array(
                    [[timestamp, price, amount, message.update_id]
                     for price, amount in [self.get_rates_and_amts_with_ids(entry, id_list) for entry in entries]
                     if price is not None],
                    dtype="float64", ndmin=2
                )
        return nps['bids'], nps['asks']

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        cdef:
            float price
            float amount
            str order_id
            dict order_dict

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()
        timestamp = message.timestamp
        content = message.content
        content_keys = list(content.keys())

        if "bids" in content_keys:
            for snapshot_orders, active_orders in [(content["bids"], self._active_bids), (content["asks"], self._active_asks)]:
                for entry in snapshot_orders:
                    price, amount = self.get_rates_and_quantities(entry)
                    active_orders[price] = amount
        else:
            for snapshot_orders, active_orders, active_order_ids in [
                (content["b"], self._active_bids, self._active_bids_ids),
                (content["s"], self._active_asks, self._active_asks_ids)
            ]:
                for entry in snapshot_orders:
                    price, amount = self.get_rates_and_amts_with_ids(entry, active_order_ids)
                    active_orders[price] = amount

        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [[message.timestamp, float(price), float(self._active_bids[price]), message.update_id]
                 for price in sorted(self._active_bids.keys())], dtype='float64', ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp, float(price), float(self._active_asks[price]), message.update_id]
                 for price in sorted(self._active_asks.keys(), reverse=True)], dtype='float64', ndmin=2)

        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

    # This method doesn't seem to be used anywhere at all
    # cdef np.ndarray[np.float64_t, ndim=1] c_convert_trade_message_to_np_array(self, object message):
    #     cdef:
    #         double trade_type_value = 1.0 if message.content[4] == "BUY" else 2.0
    #         list content = message.content

    #     return np.array([message.timestamp, trade_type_value, float(content[1]), float(content[2])],
    #                     dtype="float64")

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
