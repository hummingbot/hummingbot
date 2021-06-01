#!/usr/bin/env python

from os.path import join, realpath
from datetime import datetime
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import logging
import unittest
from typing import (
    Any,
    Dict,
    Optional
)
from hummingbot.connector.exchange.eterbase.eterbase_order_book_tracker import EterbaseOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.exchange.eterbase.eterbase_order_book_message import EterbaseOrderBookMessage
from hummingbot.connector.exchange.eterbase.eterbase_order_book import EterbaseOrderBook
from hummingbot.core.data_type.order_book_row import OrderBookRow

test_trading_pair = "ETHEUR"


class EterbaseOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[EterbaseOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.order_book_tracker: EterbaseOrderBookTracker = EterbaseOrderBookTracker(
            trading_pairs = [test_trading_pair])
        cls.order_book_tracker.order_books[test_trading_pair] = EterbaseOrderBook()

    def test_diff_message_not_found(self):
        test_active_order_tracker = self.order_book_tracker._active_order_trackers[test_trading_pair]
        test_order_book: OrderBook = EterbaseOrderBook()

        # receive match message that is not in active orders (should be ignored)
        match_msg_to_ignore: Dict[str, Any] = {
            "type": "o_fill",
            "tradeId": 10,
            "orderId": "ac928c66-ca53-498f-9c13-a110027a60e8",
            "timestamp": int(datetime.now().timestamp() * 1000),
            "marketId": 51,
            "qty": "5.23512",
            "price": "400.23",
            "side": 1
        }
        ignore_msg: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(match_msg_to_ignore)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(ignore_msg)
        self.assertEqual(open_ob_row, ([], []))

    def test_buy_diff_message(self):
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books[test_trading_pair]
        test_active_order_tracker = self.order_book_tracker._active_order_trackers[test_trading_pair]

        # receive open buy message to be added to active orders
        order_id = "abc"
        side = 1
        price = 1337.0
        open_size = 100.0
        market_id = 51
        open_sequence = int(datetime.now().timestamp() * 1000)
        open_message_dict: Dict[str, Any] = {
            "type": "o_placed",
            "timestamp": open_sequence,
            "marketId": market_id,
            "orderId": order_id,
            "limitPrice": str(price),
            "qty": str(open_size),
            "oType": 2,
            "side": side
        }
        open_message: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(open_message_dict)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(open_message)
        self.assertEqual(open_ob_row[0], [OrderBookRow(price, open_size, open_sequence)])

        # receive match message
        match_size = 30.0
        match_sequence = int(datetime.now().timestamp() * 1000)
        match_message_dict: Dict[str, Any] = {
            "type": "o_fill",
            "tradeId": 10,
            "orderId": order_id,
            "timestamp": match_sequence,
            "marketId": market_id,
            "qty": str(match_size),
            "remainingQty": str(open_size - match_size),
            "limitPrice": str(price),
            "side": side
        }
        match_message: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(match_message_dict)

        match_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(match_message)
        self.assertEqual(match_ob_row[0], [OrderBookRow(price, open_size - match_size, match_sequence)])

        # receive done message
        done_size = 0.0
        done_sequence = int(datetime.now().timestamp() * 1000)
        done_message_dict: Dict[str, Any] = {
            "type": "o_closed",
            "timestamp": done_sequence,
            "marketId": market_id,
            "price": str(price),
            "orderId": order_id,
            "closeReason": "FILLED",
            "side": side,
            "remainingQty": "0"
        }
        done_message: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(done_message_dict)

        done_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(done_message)
        self.assertEqual(done_ob_row[0], [OrderBookRow(price, done_size, done_sequence)])

    def test_sell_diff_message(self):
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books[test_trading_pair]
        test_active_order_tracker = self.order_book_tracker._active_order_trackers[test_trading_pair]

        # receive open sell message to be added to active orders
        order_id = "abc"
        side = 2
        price = 1337.0
        open_size = 100.0
        open_sequence = int(datetime.now().timestamp() * 1000)
        market_id = 51
        open_message_dict: Dict[str, Any] = {
            "type": "o_placed",
            "timestamp": open_sequence,
            "marketId": market_id,
            "orderId": order_id,
            "price": str(price),
            "qty": str(open_size),
            "oType": 2,
            "side": side
        }
        open_message: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(open_message_dict)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(open_message)
        self.assertEqual(open_ob_row[1], [OrderBookRow(price, open_size, open_sequence)])

        # receive open sell message to be added to active orders
        order_id_2 = "def"
        side = 2
        price = 1337.0
        open_size_2 = 100.0
        open_sequence_2 = int(datetime.now().timestamp() * 1000)
        open_message_dict_2: Dict[str, Any] = {
            "type": "o_placed",
            "timestamp": open_sequence_2,
            "marketId": market_id,
            "orderId": order_id_2,
            "limitPrice": str(price),
            "qty": str(open_size_2),
            "oType": 2,
            "side": side
        }
        open_message: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(open_message_dict_2)
        open_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(open_message)
        self.assertEqual(open_ob_row[1], [OrderBookRow(price, open_size + open_size_2, open_sequence_2)])

        # receive match message
        match_size = 30.0
        match_sequence = int(datetime.now().timestamp() * 1000)
        match_message_dict: Dict[str, Any] = {
            "type": "o_fill",
            "tradeId": 10,
            "orderId": order_id,
            "timestamp": match_sequence,
            "marketId": market_id,
            "qty": str(match_size),
            "price": str(price),
            "side": side,
            "remainingQty": str(open_size_2 - match_size)
        }
        match_message: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(match_message_dict)

        match_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(match_message)
        self.assertEqual(match_ob_row[1], [OrderBookRow(price, open_size + open_size_2 - match_size, match_sequence)])

        # receive done message
        done_size = 0.0
        done_sequence = int(datetime.now().timestamp() * 1000)
        done_message_dict: Dict[str, Any] = {
            "type": "o_closed",
            "timestamp": done_sequence,
            "marketId": market_id,
            "price": str(price),
            "orderId": order_id,
            "closeReason": "FILLED",
            "side": side,
        }
        done_message: EterbaseOrderBookMessage = test_order_book.diff_message_from_exchange(done_message_dict)

        done_ob_row: OrderBookRow = test_active_order_tracker.convert_diff_message_to_order_book_row(done_message)
        self.assertEqual(done_ob_row[1], [OrderBookRow(price, done_size + open_size_2, done_sequence)])


def main():
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()


if __name__ == "__main__":
    main()
