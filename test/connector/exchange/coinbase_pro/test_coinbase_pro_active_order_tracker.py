#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import logging
import unittest
from typing import (
    Any,
    Dict,
    Optional
)
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_message import CoinbaseProOrderBookMessage
from hummingbot.core.data_type.order_book_row import OrderBookRow

test_trading_pair = "BTC-USD"


class CoinbaseProOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[CoinbaseProOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.order_book_tracker: CoinbaseProOrderBookTracker = CoinbaseProOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API,
            trading_pairs=[test_trading_pair])

    def test_diff_message_not_found(self):
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books[test_trading_pair]
        test_active_order_tracker = self.order_book_tracker._active_order_trackers[test_trading_pair]

        # receive match message that is not in active orders (should be ignored)
        match_msg_to_ignore: Dict[str, Any] = {
            "type": "match",
            "trade_id": 10,
            "sequence": 50,
            "maker_order_id": "ac928c66-ca53-498f-9c13-a110027a60e8",
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "size": "5.23512",
            "price": "400.23",
            "side": "sell"
        }
        ignore_msg: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(match_msg_to_ignore)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(ignore_msg)
        self.assertEqual(open_ob_row, ([], []))

    def test_buy_diff_message(self):
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books[test_trading_pair]
        test_active_order_tracker = self.order_book_tracker._active_order_trackers[test_trading_pair]

        # receive open buy message to be added to active orders
        order_id = "abc"
        side = "buy"
        price = 1337.0
        open_size = 100.0
        open_sequence = 1
        open_message_dict: Dict[str, Any] = {
            "type": "open",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "sequence": open_sequence,
            "order_id": order_id,
            "price": str(price),
            "remaining_size": str(open_size),
            "side": side
        }
        open_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(open_message_dict)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(open_message)
        self.assertEqual(open_ob_row[0], [OrderBookRow(price, open_size, open_sequence)])

        # receive change message
        change_size = 50.0
        change_sequence = 2
        change_message_dict: Dict[str, Any] = {
            "type": "change",
            "time": "2014-11-07T08:19:27.028459Z",
            "sequence": change_sequence,
            "order_id": order_id,
            "product_id": test_trading_pair,
            "new_size": str(change_size),
            "old_size": "100.0",
            "price": str(price),
            "side": side
        }
        change_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(change_message_dict)

        change_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(change_message)
        self.assertEqual(change_ob_row[0], [OrderBookRow(price, change_size, change_sequence)])

        # receive match message
        match_size = 30.0
        match_sequence = 3
        match_message_dict: Dict[str, Any] = {
            "type": "match",
            "trade_id": 10,
            "sequence": match_sequence,
            "maker_order_id": order_id,
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "size": str(match_size),
            "price": str(price),
            "side": side
        }
        match_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(match_message_dict)

        match_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(match_message)
        self.assertEqual(match_ob_row[0], [OrderBookRow(price, change_size - match_size, match_sequence)])

        # receive done message
        done_size = 0.0
        done_sequence = 4
        done_message_dict: Dict[str, Any] = {
            "type": "done",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "sequence": done_sequence,
            "price": str(price),
            "order_id": order_id,
            "reason": "filled",
            "side": side,
            "remaining_size": "0"
        }
        done_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(done_message_dict)

        done_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(done_message)
        self.assertEqual(done_ob_row[0], [OrderBookRow(price, done_size, done_sequence)])

    def test_sell_diff_message(self):
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books[test_trading_pair]
        test_active_order_tracker = self.order_book_tracker._active_order_trackers[test_trading_pair]

        # receive open sell message to be added to active orders
        order_id = "abc"
        side = "sell"
        price = 1337.0
        open_size = 100.0
        open_sequence = 1
        open_message_dict: Dict[str, Any] = {
            "type": "open",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "sequence": open_sequence,
            "order_id": order_id,
            "price": str(price),
            "remaining_size": str(open_size),
            "side": side
        }
        open_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(open_message_dict)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(open_message)
        self.assertEqual(open_ob_row[1], [OrderBookRow(price, open_size, open_sequence)])

        # receive open sell message to be added to active orders
        order_id_2 = "def"
        side = "sell"
        price = 1337.0
        open_size_2 = 100.0
        open_sequence_2 = 2
        open_message_dict_2: Dict[str, Any] = {
            "type": "open",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "sequence": open_sequence_2,
            "order_id": order_id_2,
            "price": str(price),
            "remaining_size": str(open_size),
            "side": side
        }
        open_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(open_message_dict_2)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(open_message)
        self.assertEqual(open_ob_row[1], [OrderBookRow(price, open_size + open_size_2, open_sequence_2)])

        # receive change message
        change_size = 50.0
        change_sequence = 3
        change_message_dict: Dict[str, Any] = {
            "type": "change",
            "time": "2014-11-07T08:19:27.028459Z",
            "sequence": change_sequence,
            "order_id": order_id,
            "product_id": test_trading_pair,
            "new_size": str(change_size),
            "old_size": "100.0",
            "price": str(price),
            "side": side
        }
        change_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(change_message_dict)

        change_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(change_message)
        self.assertEqual(change_ob_row[1], [OrderBookRow(price, change_size + open_size_2, change_sequence)])

        # receive match message
        match_size = 30.0
        match_sequence = 4
        match_message_dict: Dict[str, Any] = {
            "type": "match",
            "trade_id": 10,
            "sequence": match_sequence,
            "maker_order_id": order_id,
            "taker_order_id": "132fb6ae-456b-4654-b4e0-d681ac05cea1",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "size": str(match_size),
            "price": str(price),
            "side": side
        }
        match_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(match_message_dict)

        match_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(match_message)
        self.assertEqual(match_ob_row[1], [OrderBookRow(price, change_size - match_size + open_size_2, match_sequence)])

        # receive done message
        done_size = 0.0
        done_sequence = 5
        done_message_dict: Dict[str, Any] = {
            "type": "done",
            "time": "2014-11-07T08:19:27.028459Z",
            "product_id": test_trading_pair,
            "sequence": done_sequence,
            "price": str(price),
            "order_id": order_id,
            "reason": "filled",
            "side": side,
            "remaining_size": "0"
        }
        done_message: CoinbaseProOrderBookMessage = test_order_book.diff_message_from_exchange(done_message_dict)

        done_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(done_message)
        self.assertEqual(done_ob_row[1], [OrderBookRow(price, done_size + open_size_2, done_sequence)])


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
