#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

from collections import defaultdict
from decimal import Decimal
import pandas as pd
from typing import (
    List,
    Dict
)
import unittest

import hummingsim
from hummingsim.backtest.ddex_order_book_loader import DDEXOrderBookLoader
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


class DDEXOrderBookLoaderUnitTest(unittest.TestCase):
    start_time: float = pd.Timestamp("2018-12-03", tz="UTC").timestamp()
    end_time: float = pd.Timestamp("2018-12-04", tz="UTC").timestamp()
    snapshot_time: float = pd.Timestamp("2018-12-03 01:19:15.563000", tz="UTC").timestamp()

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, start_time=self.start_time, end_time=self.end_time)
        self.order_book_loader: DDEXOrderBookLoader = DDEXOrderBookLoader("WETH-DAI", "WETH", "DAI")
        self.order_book: OrderBook = self.order_book_loader.order_book
        self.clock.add_iterator(self.order_book_loader)

    def tearDown(self):
        self.order_book_loader.close()

    def test_messages_ordering(self):
        messages: List[OrderBookMessage] = self.order_book_loader.fetch_order_book_messages(self.start_time,
                                                                                            self.end_time)
        snapshots: List[OrderBookMessage] = [m for m in messages if m.type.value == 1]
        diffs: List[OrderBookMessage] = [m for m in messages if m.type.value == 2]
        trades: List[OrderBookMessage] = [m for m in messages if m.type.value == 3]
        timestamps: pd.Series = pd.Series([m.timestamp for m in messages])

        timestamp_diffs: pd.Series = pd.Series(timestamps[1:].values - timestamps[0:-1].values)
        self.assertTrue(all(timestamp_diffs >= 0))
        self.assertGreater(timestamp_diffs.mean(), 0)
        self.assertGreater(len(snapshots), 0)
        self.assertGreater(len(trades), 0)
        self.assertGreater(len(diffs), 0)

    def test_order_book_snapshots(self):
        self.clock.backtest_til(int(self.snapshot_time))
        pre_bids, pre_asks = self.order_book.snapshot
        self.clock.backtest_til(int(self.snapshot_time) + 1)
        post_bids, post_asks = self.order_book.snapshot

        self.assertGreater(len(pre_bids), 0)
        matching, total = OrderBookUtils.compare_books(pre_bids, post_bids)
        self.assertLess(total - matching, 10)

        self.assertGreater(len(pre_asks), 10)
        matching, total = OrderBookUtils.compare_books(pre_asks, post_asks)
        self.assertLess(total - matching, 10)

    def test_order_book_diffs(self):
        start: int = int(self.snapshot_time) + 1
        end: int = int(self.snapshot_time) + 1800
        self.clock.backtest_til(start)
        pre_bids, pre_asks = self.order_book.snapshot
        self.clock.backtest_til(end)
        post_bids, post_asks = self.order_book.snapshot

        book_messages: List[OrderBookMessage] = [
            message
            for message in self.order_book_loader.fetch_order_book_messages(start - 1, end)
            if message.type in {OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT}
        ]
        bids_map: Dict[Decimal, Dict[str, Dict[str, any]]] = defaultdict(lambda: {})
        asks_map: Dict[Decimal, Dict[str, Dict[str, any]]] = defaultdict(lambda: {})

        for msg in book_messages:
            if msg.type is OrderBookMessageType.DIFF:
                book_map: Dict[Decimal, Dict[str, Dict[str, any]]] = bids_map
                if msg.content["side"] == "sell":
                    book_map = asks_map
                msg_type: str = msg.content["type"]
                price: Decimal = Decimal(msg.content["price"])
                order_id: str = msg.content["orderId"]
                if msg_type == "receive":
                    book_map[price][order_id] = msg.content
                elif msg_type == "done":
                    if order_id in book_map[price]:
                        del book_map[price][order_id]
            elif msg.type is OrderBookMessageType.SNAPSHOT:
                bids_map.clear()
                asks_map.clear()
                for bid_entry in msg.content["bids"]:
                    order_id: str = bid_entry["orderId"]
                    price: Decimal = Decimal(bid_entry["price"])
                    amount: str = bid_entry["amount"]
                    bids_map[price][order_id] = {"orderId": order_id, "availableAmount": amount}
                for ask_entry in msg.content["asks"]:
                    order_id: str = ask_entry["orderId"]
                    price: Decimal = Decimal(ask_entry["price"])
                    amount: str = ask_entry["amount"]
                    asks_map[price][order_id] = {"orderId": order_id, "availableAmount": amount}

        compare_bids: pd.DataFrame = OrderBookUtils.get_compare_df(pre_bids, post_bids, diffs_only=True)
        compare_asks: pd.DataFrame = OrderBookUtils.get_compare_df(pre_asks, post_asks, diffs_only=True)
        compare_bids.fillna(value=0.0, inplace=True)
        compare_asks.fillna(value=0.0, inplace=True)

        self.assertGreater(len(compare_bids), 0)
        self.assertGreater(len(compare_asks), 0)

        post_bids.set_index("price", inplace=True)
        post_asks.set_index("price", inplace=True)

        for price, orders in bids_map.items():
            total_amount: float = 0
            if len(orders) > 0:
                total_amount = sum(float(item["availableAmount"]) for item in orders.values())
            if total_amount == 0:
                self.assertTrue(float(price) not in post_bids.index,
                                f"{price} should not exist in the post_bids snapshot.")
            else:
                self.assertTrue(float(price) in post_bids.index,
                                f"{price} should exist in the post_bids snapshot.")
                self.assertAlmostEqual(float(total_amount), post_bids.loc[float(price)].amount,
                                       f"total amount for {price} should be {total_amount}.")

        for price, orders in asks_map.items():
            total_amount: float = 0
            if len(orders) > 0:
                total_amount = sum(float(item["availableAmount"]) for item in orders.values())
            if total_amount == 0:
                self.assertTrue(float(price) not in post_asks.index,
                                f"{price} should not exist in the post_asks snapshot.")
            else:
                self.assertTrue(float(price) in post_asks.index,
                                f"{price} should exist in the post_asks snapshot.")
                self.assertAlmostEqual(total_amount, post_asks.loc[float(price)].amount,
                                       f"total amount for {price} should be {total_amount}.")

    def test_order_book_trades(self):
        start: int = int(self.snapshot_time)
        end: int = int(self.snapshot_time) + 86400
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
        self.assertGreater(len(trade_messages), 0)
        self.assertEqual(len(trade_messages), len(events))
        for trade_message, trade_event in zip(trade_messages, events):
            self.assertAlmostEqual(trade_message.timestamp, trade_event.timestamp)
            self.assertAlmostEqual(float(trade_message.content["price"]), trade_event.price)
            self.assertAlmostEqual(float(trade_message.content["amount"]), trade_event.amount)


if __name__ == "__main__":
    hummingsim.set_data_path(realpath(join(__file__, "../../data")))
    unittest.main()
