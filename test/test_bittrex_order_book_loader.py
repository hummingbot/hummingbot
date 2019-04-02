#!/usr/bin/env python

from os.path import join, realpath
import sys;


sys.path.insert(0, realpath(join(__file__, "../../")))
from hummingsim.backtest.bittrex_order_book_loader import BittrexOrderBookLoader
import logging

import pandas as pd
from typing import (
    List,
    Optional)
import unittest

import hummingsim
from hummingsim.backtest.huobi_order_book_loader import HuobiOrderBookLoader
from wings.clock import (
    Clock,
    ClockMode
)
from wings.events import (
    OrderBookTradeEvent,
    OrderBookEvent,
)
from wings.order_book import OrderBook
from wings.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

from test import OrderBookUtils
from wings.event_logger import EventLogger


class BittrexOrderBookLoaderUnitTest(unittest.TestCase):
    start_time: float = pd.Timestamp("2018-12-11", tz="UTC").timestamp()
    end_time: float = pd.Timestamp("2018-12-12", tz="UTC").timestamp()
    snapshot_time: float = pd.Timestamp("2018-12-11 01:00:00.444000", tz="UTC").timestamp()

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, start_time=self.start_time, end_time=self.end_time)
        self.order_book_loader: BittrexOrderBookLoader = BittrexOrderBookLoader("USDT-BTC", "BTC", "USDT")
        self.order_book: OrderBook = self.order_book_loader.order_book
        self.clock.add_iterator(self.order_book_loader)

    def tearDown(self):
        self.order_book_loader.close()

    def test_order_book_snapshots(self):
        self.clock.backtest_til(int(self.snapshot_time))
        pre_bids, pre_asks = self.order_book.snapshot
        self.clock.backtest_til(int(self.snapshot_time) + 1)
        post_bids, post_asks = self.order_book.snapshot

        matching, total = OrderBookUtils.compare_books(pre_bids, post_bids)
        self.assertLess(total - matching, 50)

        matching, total = OrderBookUtils.compare_books(pre_asks, post_asks)
        self.assertLess(total - matching, 50)

    def test_order_book_diffs(self):
        """
        test multiple timeframe each right after hourly snapshots
        """

        def _test_order_book_diffs(start: int, end: int):
            """
            Test 1: last non-zero amount (removed) order message appears correctly in the end snapshot.

            Test 2: last zero amount order message are valid if both start and end snapshot do not have it,
            or the end snapshot shows that it is removed.

            """
            bid_message: Optional[OrderBookMessage] = None
            ask_message: Optional[OrderBookMessage] = None
            last_bid_diffs: Optional[pd.DataFrame] = pd.DataFrame()
            last_ask_diffs: Optional[pd.DataFrame] = pd.DataFrame()

            self.clock.backtest_til(start)
            pre_bids, pre_asks = self.order_book.snapshot
            self.clock.backtest_til(end)
            post_bids, post_asks = self.order_book.snapshot

            compare_bids: pd.DataFrame = OrderBookUtils.get_compare_df(pre_bids, post_bids, n_rows=800, diffs_only=True)
            compare_asks: pd.DataFrame = OrderBookUtils.get_compare_df(pre_asks, post_asks, n_rows=800, diffs_only=True)
            compare_bids.fillna(value=0.0, inplace=True)
            compare_asks.fillna(value=0.0, inplace=True)

            bid_messages: List[OrderBookMessage] = [
                message for message in self.order_book_loader.fetch_order_book_messages(start, end)
                if message.type is OrderBookMessageType.DIFF
                and len(message.content["bids"]) > 0
            ]
            ask_messages: List[OrderBookMessage] = [
                message for message in self.order_book_loader.fetch_order_book_messages(start, end)
                if message.type is OrderBookMessageType.DIFF
                and len(message.content["asks"]) > 0
            ]

            if len(bid_messages) > 0:
                bid_message = bid_messages[-1]
            if len(ask_messages) > 0:
                ask_message = ask_messages[-1]

            if bid_message and bid_message.timestamp > start:
                last_bid_diffs: pd.DataFrame = pd.DataFrame.from_records(
                    data=[[float(row[0]), float(row[1])] for row in bid_message.content["bids"]],
                    columns=["price", "amount"],
                    index="price"
                )
                self.assertGreater(len(compare_bids), 0)

            if ask_message and ask_message.timestamp > start:
                last_ask_diffs: pd.DataFrame = pd.DataFrame.from_records(
                    data=[[float(row[0]), float(row[1])] for row in ask_message.content["asks"]],
                    columns=["price", "amount"],
                    index="price"
                )
                self.assertGreater(len(compare_asks), 0)

            for row in last_bid_diffs.itertuples():
                if row.amount == 0:
                    self.assertTrue(
                        (row.Index not in pre_bids.price and row.Index not in post_bids.price)
                        or row.Index in compare_bids.Index
                    )
                    continue

                self.assertTrue(row.Index in set(post_bids.price))
                self.assertEqual(post_bids.loc[post_bids["price"] == row.Index].amount.values[0], row.amount)

            for row in last_ask_diffs.itertuples():
                if row.amount == 0:
                    self.assertTrue(
                        (row.Index not in pre_asks.price and row.Index not in post_asks.price)
                        or row.Index in compare_asks.Index
                    )
                    continue

                self.assertTrue(row.Index in set(post_asks.price))
                self.assertEqual(post_asks.loc[post_asks["price"] == row.Index].amount.values[0], row.amount)

        for hour in range(6):
            start: int = int(self.snapshot_time) + hour*60*60
            end: int = start + 60
            _test_order_book_diffs(start, end)

    def test_order_book_trades(self):
        start: int = int(self.snapshot_time) + 1
        end: int = int(self.snapshot_time) + 60
        self.clock.backtest_til(start)

        event_recorder: EventLogger = EventLogger()
        self.order_book.add_listener(OrderBookEvent.TradeEvent, event_recorder)
        self.clock.backtest_til(end)

        trade_messages: List[OrderBookMessage] = [
            message
            for message in self.order_book_loader.fetch_order_book_messages(start, end)
            if message.type is OrderBookMessageType.TRADE
        ]

        events: List[OrderBookTradeEvent] = event_recorder.event_log
        self.assertEqual(len(trade_messages), len(events))
        for trade_message, trade_event in zip(trade_messages, events):
            self.assertAlmostEqual(trade_message.timestamp, trade_event.timestamp)
            self.assertAlmostEqual(float(trade_message.content["price"]), trade_event.price)
            self.assertAlmostEqual(float(trade_message.content["amount"]), trade_event.amount)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hummingsim.set_data_path(realpath(join(__file__, "../../data")))
    unittest.main()

