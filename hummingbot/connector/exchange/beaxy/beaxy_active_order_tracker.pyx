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

ACTION_UPDATE = 'update'
ACTION_INSERT = 'insert'
ACTION_DELETE = 'delete'
ACTION_DELETE_THROUGH = 'delete_through'
ACTION_DELETE_FROM = 'delete_from'
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

    cdef tuple c_convert_diff_message_to_np_arrays(self, object message):
        """
        Interpret an incoming diff message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """

        cdef:
            dict content = message.content
            str msg_action = content['action'].lower()
            str order_side = content['side']
            str price_raw = str(content['price'])
            double timestamp = message.timestamp
            str quantity_raw = str(content['quantity'])
            object price
            object quantity

        if order_side not in [SIDE_BID, SIDE_ASK]:
            raise ValueError(f'Unknown order side for message - "{message}". Aborting.')

        price = Decimal(price_raw)
        quantity = Decimal(quantity_raw)

        if msg_action == ACTION_UPDATE:
            if order_side == SIDE_BID:
                self._active_bids[price] = quantity
                return np.array([[timestamp, float(price), quantity, message.update_id]], dtype='float64'), s_empty_diff
            else:
                self._active_asks[price] = quantity
                return s_empty_diff, np.array([[timestamp, float(price), quantity, message.update_id]], dtype='float64')

        elif msg_action == ACTION_INSERT:
            if price in self._active_bids or price in self._active_asks:
                raise ValueError(f'Got INSERT action in message - "{message}" but there already was an item with same price. Aborting.')

            if order_side == SIDE_BID:
                self._active_bids[price] = quantity
                return np.array([[timestamp, float(price), quantity, message.update_id]], dtype='float64'), s_empty_diff
            else:
                self._active_asks[price] = quantity
                return s_empty_diff, np.array([[timestamp, float(price), quantity, message.update_id]], dtype='float64')
        elif msg_action == ACTION_DELETE:
            # in case of DELETE action we need to substract the provided quantity from existing one
            if price not in self._active_bids and price not in self._active_asks:
                raise ValueError(f'Got DELETE action in message - "{message}" but there was not entry with that price. Aborting.')

            if order_side == SIDE_BID:
                new_quantity = self._active_bids[price] - quantity
                self._active_bids[price] = new_quantity
                return np.array([[timestamp, float(price), new_quantity, message.update_id]], dtype='float64'), s_empty_diff
            else:
                new_quantity = self._active_asks[price] - quantity
                self._active_asks[price] = new_quantity
                return s_empty_diff, np.array([[timestamp, float(price), new_quantity, message.update_id]], dtype='float64')
        elif msg_action == ACTION_DELETE_THROUGH:
            # Remove all levels from the specified and below (all the worst prices).
            if order_side == SIDE_BID:
                self._active_bids = {key: value for (key, value) in self._active_bids.items() if key < price}
                return s_empty_diff, s_empty_diff
            else:
                self._active_asks = {key: value for (key, value) in self._active_asks.items() if key < price}
                return s_empty_diff, s_empty_diff
        elif msg_action == ACTION_DELETE_FROM:
            # Remove all levels from the specified and above (all the better prices).
            if order_side == SIDE_BID:
                self._active_bids = {key: value for (key, value) in self._active_bids.items() if key > price}
                return s_empty_diff, s_empty_diff
            else:
                self._active_asks = {key: value for (key, value) in self._active_asks.items() if key > price}
                return s_empty_diff, s_empty_diff
        else:
            raise ValueError(f'Unknown message action "{msg_action}" - {message}. Aborting.')

    cdef tuple c_convert_snapshot_message_to_np_arrays(self, object message):
        """
        Interpret an incoming snapshot message and apply changes to the order book accordingly
        :returns: new order book rows: Tuple(np.array (bids), np.array (asks))
        """

        # Refresh all order tracking.
        self._active_bids.clear()
        self._active_asks.clear()

        for entry in message.content['entries']:
            quantity = Decimal(str(entry['quantity']))
            price = Decimal(str(entry['price']))
            side = entry['side']

            if side == SIDE_ASK:
                self.active_asks[price] = quantity
            elif side == SIDE_BID:
                self.active_bids[price] = quantity
            else:
                raise ValueError(f'Unknown order side for message - "{message}". Aborting.')

        # Return the sorted snapshot tables.
        cdef:
            np.ndarray[np.float64_t, ndim=2] bids = np.array(
                [[message.timestamp,
                  float(price),
                  float(quantity),
                  message.update_id]
                 for price in sorted(self._active_bids.keys(), reverse=True)], dtype='float64', ndmin=2)
            np.ndarray[np.float64_t, ndim=2] asks = np.array(
                [[message.timestamp,
                  float(price),
                  float(quantity),
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
