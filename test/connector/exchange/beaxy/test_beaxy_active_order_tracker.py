#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import unittest
from typing import Any, Dict

from hummingbot.core.data_type.order_book_row import OrderBookRow
from hummingbot.connector.exchange.beaxy.beaxy_order_book_message import BeaxyOrderBookMessage
from hummingbot.connector.exchange.beaxy.beaxy_order_book import BeaxyOrderBook
from hummingbot.connector.exchange.beaxy.beaxy_active_order_tracker import BeaxyActiveOrderTracker

from test.connector.exchange.beaxy.fixture_beaxy import FixtureBeaxy


test_trading_pair = "BTC-USDC"


class BeaxyOrderBookTrackerUnitTest(unittest.TestCase):
    def test_insert_update_delete_messages(self):
        active_tracker = BeaxyActiveOrderTracker()

        # receive INSERT message to be added to active orders
        side = "BID"
        price = 1337.4423423404
        quantity: float = 1
        update_id = 123
        message_dict: Dict[str, Any] = {
            'timestamp': 1,
            'sequenceNumber': update_id,
            'entries': [{
                "action": "INSERT",
                "quantity": quantity,
                "price": price,
                "side": side,
                "sequrity": test_trading_pair
            }]
        }
        insert_message = BeaxyOrderBook.diff_message_from_exchange(message_dict, float(12345))
        insert_ob_row: OrderBookRow = active_tracker.convert_diff_message_to_order_book_row(insert_message)
        self.assertEqual(insert_ob_row[0], [OrderBookRow(price, quantity, update_id)])

        # receive UPDATE message
        updated_quantity: float = 3.2
        update_message_dict: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": update_id + 1,
            'entries': [{
                "action": "UPDATE",
                "quantity": updated_quantity,
                "price": price,
                "side": side,
                "sequrity": test_trading_pair
            }]
        }
        change_message = BeaxyOrderBook.diff_message_from_exchange(update_message_dict, float(12345))
        change_ob_row: OrderBookRow = active_tracker.convert_diff_message_to_order_book_row(change_message)
        self.assertEqual(change_ob_row[0], [OrderBookRow(price, float(updated_quantity), update_id + 1)])

        # receive DELETE message
        delete_quantity = 1
        delete_message_dict: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": update_id + 2,
            'entries': [{
                "action": "DELETE",
                "quantity": delete_quantity,
                "price": price,
                "side": side,
                "sequrity": test_trading_pair
            }]
        }

        delete_message: BeaxyOrderBookMessage = BeaxyOrderBook.diff_message_from_exchange(delete_message_dict, float(12345))
        delete_ob_row: OrderBookRow = active_tracker.convert_diff_message_to_order_book_row(delete_message)
        self.assertEqual(delete_ob_row[0], [OrderBookRow(price, float(0), update_id + 1 + 1)])

    def test_delete_through(self):
        active_tracker = BeaxyActiveOrderTracker()

        # receive INSERT message to be added to active orders
        first_insert: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 1,
            'entries': [{
                "action": "INSERT",
                "quantity": 1,
                "price": 133,
                "side": "BID",
                "sequrity": test_trading_pair,
            }]
        }
        second_insert: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 2,
            'entries': [{
                "action": "INSERT",
                "quantity": 2,
                "price": 134,
                "side": "BID",
                "sequrity": test_trading_pair
            }]
        }
        third_insert: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 1,
            'entries': [{
                "action": "INSERT",
                "quantity": 3,
                "price": 135,
                "side": "BID",
                "sequrity": test_trading_pair
            }]
        }

        inserts = [first_insert, second_insert, third_insert]
        for msg in inserts:
            insert_message = BeaxyOrderBook.diff_message_from_exchange(msg, float(12345))
            active_tracker.convert_diff_message_to_order_book_row(insert_message)

        delete_through_dict: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 1,
            'entries': [{
                "action": "DELETE_THROUGH",
                "quantity": 3,
                "price": 134,
                "side": "BID",
                "sequrity": test_trading_pair
            }]
        }

        msg = BeaxyOrderBook.diff_message_from_exchange(delete_through_dict, float(12345))
        active_tracker.convert_diff_message_to_order_book_row(msg)
        self.assertEqual(len(active_tracker.active_bids), 2)
        self.assertEqual(next(iter(active_tracker.active_bids)), 134)

    def test_delete_from(self):
        active_tracker = BeaxyActiveOrderTracker()

        # receive INSERT message to be added to active orders
        first_insert: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 1,
            'entries': [{
                "action": "INSERT",
                "quantity": 1,
                "price": 133,
                "side": "ASK",
                "sequrity": test_trading_pair
            }]
        }
        second_insert: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 2,
            'entries': [{
                "action": "INSERT",
                "quantity": 2,
                "price": 134,
                "side": "ASK",
                "sequrity": test_trading_pair
            }]
        }
        third_insert: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 1,
            'entries': [{
                "action": "INSERT",
                "quantity": 3,
                "price": 135,
                "side": "ASK",
                "sequrity": test_trading_pair
            }]
        }

        inserts = [first_insert, second_insert, third_insert]
        for msg in inserts:
            insert_message = BeaxyOrderBook.diff_message_from_exchange(msg, float(12345))
            active_tracker.convert_diff_message_to_order_book_row(insert_message)

        delete_through_dict: Dict[str, Any] = {
            'timestamp': 1,
            "sequenceNumber": 1,
            'entries': [{
                "action": "DELETE_FROM",
                "quantity": 3,
                "price": 134,
                "side": "ASK",
                "sequrity": test_trading_pair
            }]
        }

        msg = BeaxyOrderBook.diff_message_from_exchange(delete_through_dict, float(12345))
        active_tracker.convert_diff_message_to_order_book_row(msg)
        self.assertEqual(len(active_tracker.active_asks), 2)
        self.assertEqual(next(iter(active_tracker.active_asks)), 133)

    def test_snapshot(self):
        active_tracker = BeaxyActiveOrderTracker()
        insert_message = BeaxyOrderBook.snapshot_message_from_exchange(FixtureBeaxy.SNAPSHOT_MSG, float(12345))

        active_tracker.convert_snapshot_message_to_order_book_row(insert_message)

        self.assertEqual(len(active_tracker.active_asks), 9)
