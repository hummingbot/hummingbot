# -*- coding: utf-8 -*-

# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/OrderBookEntry.cpp

import logging
import numpy as np
from decimal import Decimal
from typing import Dict

from hummingbot.logger import HummingbotLogger
from hummingbot.core.data_type.order_book_row import OrderBookRow

_bxaot_logger = None
s_empty_diff = np.ndarray(shape=(0, 4), dtype='float64')

BeaxyOrderBookTrackingDictionary = Dict[Decimal, Decimal]

ACTION_UPDATE = 'UPDATE'
ACTION_INSERT = 'INSERT'
ACTION_DELETE = 'DELETE'
ACTION_DELETE_THROUGH = 'DELETE_THROUGH'
ACTION_DELETE_FROM = 'DELETE_FROM'
SIDE_BID = 'BID'
SIDE_ASK = 'ASK'

cdef class BeaxyActiveOrderTracker:
    def __init__(self,
                 active_asks: BeaxyOrderBookTrackingDictionary = None,
                 active_bids: BeaxyOrderBookTrackingDictionary = None):
        super().__init__()
        self._active_asks = active_asks or {}
        self._active_bids = active_bids or {}

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global _bxaot_logger
        if _bxaot_logger is None:
            _bxaot_logger = logging.getLogger(__name__)
        return _bxaot_logger

    @property
    def active_asks(self) -> BeaxyOrderBookTrackingDictionary:
        """
        Get all asks on the order book in dictionary format
        :returns: Dict[price, Dict[order_id, order_book_message]]
        """
        return self._active_asks

    @property
    def active_bids(self) -> BeaxyOrderBookTrackingDictionary:
        """
        Get all bids on the order book in dictionary format
        :returns: Dict[price, Dict[order_id, order_book_message]]
        """
        return self._active_bids

    def volume_for_ask_price(self, price) -> float:
        return sum([float(msg['remaining_size']) for msg in self._active_asks[price].values()])

    def volume_for_bid_price(self, price) -> float:
        return sum([float(msg['remaining_size']) for msg in self._active_bids[price].values()])

    def get_rates_and_quantities(self, entry) -> tuple:
        return float(entry['rate']), float(entry['quantity'])

    def is_entry_valid(self, entry):
        return all([k in entry for k in ['side', 'action', 'price']])

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        """
        Interpret an incoming diff message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """

        def diff(side):

            for entry in message.content['entries']:

                if not self.is_entry_valid(entry):
                    continue

                if entry['side'] != side:
                    continue

                msg_action = entry['action']
                order_side = entry['side']
                timestamp = message.timestamp

                price = Decimal(str(entry['price']))

                active_rows = self._active_bids if order_side == SIDE_BID else self._active_asks

                if msg_action in (ACTION_UPDATE, ACTION_INSERT):

                    if 'quantity' not in entry:
                        continue

                    quantity = Decimal(str(entry['quantity']))

                    active_rows[price] = quantity
                    yield [timestamp, float(price), quantity, message.update_id]

                elif msg_action == ACTION_DELETE:

                    if price not in active_rows:
                        continue

                    del active_rows[price]
                    yield [timestamp, float(price), float(0), message.update_id]

                elif msg_action == ACTION_DELETE_THROUGH:
                    # Remove all levels from the specified and below (all the worst prices).
                    for key in list(active_rows.keys()):
                        if key < price:
                            del active_rows[key]
                            yield [timestamp, float(price), float(0), message.update_id]

                elif msg_action == ACTION_DELETE_FROM:
                    # Remove all levels from the specified and above (all the better prices).
                    for key in list(active_rows.keys()):
                        if key > price:
                            del active_rows[key]
                            yield [timestamp, float(price), float(0), message.update_id]

                else:
                    continue

        bids = np.array([r for r in diff(SIDE_BID)], dtype='float64', ndmin=2)
        asks = np.array([r for r in diff(SIDE_ASK)], dtype='float64', ndmin=2)

        # If there're no rows, the shape would become (1, 0) and not (0, 4).
        # Reshape to fix that.
        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        """
        Interpret an incoming snapshot message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()

        for entry in message.content['entries']:

            if not self.is_entry_valid(entry):
                continue

            quantity = Decimal(str(entry['quantity']))
            price = Decimal(str(entry['price']))
            side = entry['side']

            if side == SIDE_ASK:
                self.active_asks[price] = quantity
            elif side == SIDE_BID:
                self.active_bids[price] = quantity
            else:
                continue

        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [[message.timestamp,
                  float(price),
                  float(self._active_bids[price]),
                  message.update_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype='float64', ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  float(price),
                  float(self._active_asks[price]),
                  message.update_id]
                 for price in sorted(self._active_asks.keys(), reverse=True)], dtype='float64', ndmin=2)

        # If there're no rows, the shape would become (1, 0) and not (0, 4).
        # Reshape to fix that.
        if bids.shape[1] != 4:
            bids = bids.reshape((0, 4))
        if asks.shape[1] != 4:
            asks = asks.reshape((0, 4))

        return bids, asks

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
