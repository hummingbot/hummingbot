#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import pandas as pd
from typing import (
    List,
)
import unittest

import hummingsim
from hummingsim.backtest.binance_order_book_loader_v2 import BinanceOrderBookLoaderV2
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


class BinanceOrderBookLoaderUnitTest(unittest.TestCase):
    start_time: float = pd.Timestamp("2018-09-01", tz="UTC").timestamp()
    end_time: float = pd.Timestamp("2018-09-01 02:01:00", tz="UTC").timestamp()
    snapshot_time: float = pd.Timestamp("2018-09-01 01:00:00.68", tz="UTC").timestamp()

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, start_time=self.start_time, end_time=self.end_time)
        self.order_book_loader: BinanceOrderBookLoaderV2 = BinanceOrderBookLoaderV2("BTCUSDT", "BTC", "USDT")
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
        self.assertLess(total - matching, 10)

        matching, total = OrderBookUtils.compare_books(pre_asks, post_asks)
        self.assertLess(total - matching, 10)

    def test_order_book_diffs(self):
        start: int = int(self.snapshot_time) + 1
        end: int = int(self.snapshot_time) + 2
        self.clock.backtest_til(start)
        pre_bids, pre_asks = self.order_book.snapshot
        self.clock.backtest_til(end)
        post_bids, post_asks = self.order_book.snapshot

        diff_message: OrderBookMessage = [message
                                          for message in self.order_book_loader.fetch_order_book_messages(start, end)
                                          if message.type is OrderBookMessageType.DIFF][0]
        bid_diffs: pd.DataFrame = pd.DataFrame.from_records(data=[[float(row[0]), float(row[1])]
                                                                  for row in diff_message.content["bids"]],
                                                            columns=["price", "amount"],
                                                            index="price")
        ask_diffs: pd.DataFrame = pd.DataFrame.from_records(data=[[float(row[0]), float(row[1])]
                                                                  for row in diff_message.content["asks"]],
                                                            columns=["price", "amount"],
                                                            index="price")

        compare_bids: pd.DataFrame = OrderBookUtils.get_compare_df(pre_bids, post_bids, diffs_only=True)
        compare_asks: pd.DataFrame = OrderBookUtils.get_compare_df(pre_asks, post_asks, diffs_only=True)
        compare_bids.fillna(value=0.0, inplace=True)
        compare_asks.fillna(value=0.0, inplace=True)

        self.assertGreater(len(compare_bids), 0)
        self.assertGreater(len(compare_asks), 0)

        for row in compare_bids.itertuples():
            self.assertTrue(row.Index in bid_diffs.index)
            self.assertEqual(bid_diffs.loc[row.Index].amount, row._5)

        for row in compare_asks.itertuples():
            self.assertTrue(row.Index in ask_diffs.index)
            self.assertEqual(ask_diffs.loc[row.Index].amount, row._5)

    def test_order_book_trades(self):
        start: int = int(self.snapshot_time)
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
    hummingsim.set_data_path(realpath(join(__file__, "../../data")))
    unittest.main()
