#!/usr/bin/env python

from os.path import join, realpath
import sys;
sys.path.insert(0, realpath(join(__file__, "../../")))
from wings.orderbook.radar_relay_order_book import RadarRelayOrderBook
from wings.tracker.radar_relay_active_order_tracker import RadarRelayActiveOrderTracker
from collections import defaultdict
from decimal import Decimal
import pandas as pd
from typing import (
    List,
    Dict
)
import unittest

import hummingsim
from hummingsim.backtest.radar_relay_order_book_loader import RadarRelayOrderBookLoader
from wings.clock import (
    Clock,
    ClockMode
)
from wings.events import (
    OrderBookTradeEvent,
    OrderBookEvent,
)
from wings.order_book_message import (
    OrderBookMessage,
    OrderBookMessageType
)

from test import OrderBookUtils
from wings.event_logger import EventLogger


class RadarRelayOrderBookLoaderUnitTest(unittest.TestCase):
    start_time: float = pd.Timestamp("2019-01-12", tz="UTC").timestamp()
    end_time: float = pd.Timestamp("2019-01-13", tz="UTC").timestamp()
    snapshot_time: float = pd.Timestamp("2019-01-12 12:00:00.324", tz="UTC").timestamp()

    def setUp(self):
        self.clock: Clock = Clock(ClockMode.BACKTEST, start_time=self.start_time, end_time=self.end_time)
        self.order_book_loader: RadarRelayOrderBookLoader = RadarRelayOrderBookLoader("WETH-DAI", "WETH", "DAI")
        self.order_book: RadarRelayOrderBook = self.order_book_loader.order_book
        self.active_order_tracker: RadarRelayActiveOrderTracker = self.order_book_loader.active_order_tracker
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
        end: int = int(self.end_time)#int(self.snapshot_time) + 7200
        self.clock.backtest_til(start)
        pre_bids, pre_asks = self.order_book.snapshot
        self.clock.backtest_til(end)
        post_bids, post_asks = self.order_book.snapshot
        book_messages: List[OrderBookMessage] = [
            message
            for message in self.order_book_loader.fetch_order_book_messages(start, end)
            if message.type in {OrderBookMessageType.DIFF, OrderBookMessageType.SNAPSHOT}
        ]
        bids_map: Dict[Decimal, Dict[str, Dict[str, any]]] = defaultdict(lambda: {})
        asks_map: Dict[Decimal, Dict[str, Dict[str, any]]] = defaultdict(lambda: {})
        order_price_map: Dict[str, Decimal] = {}
        for msg in book_messages:
            if msg.type in [OrderBookMessageType.DIFF]:
                book_map: Dict[Decimal, Dict[str, Dict[str, any]]] = bids_map
                msg_type: str = msg.content["action"]
                order_side: str = ""
                order_id: str = ""
                price: Decimal = 0.0

                if msg_type in ["NEW", "FILL"]:
                    order_side = msg.content["event"]["order"]["type"]
                    order_id = msg.content["event"]["order"]["orderHash"]
                    price = Decimal(msg.content["event"]["order"]["price"])
                elif msg_type in ["CANCEL", "REMOVE"]:
                    order_side = msg.content["event"]["orderType"]
                    order_id = msg.content["event"]["orderHash"]

                if order_side == "ASK":
                    book_map = asks_map

                if msg_type == "NEW":
                    book_map[price][order_id] = {
                        "orderHash": order_id,
                        "remainingBaseTokenAmount": msg.content["event"]["order"]["remainingBaseTokenAmount"],
                        "remainingQuoteTokenAmount": msg.content["event"]["order"]["remainingQuoteTokenAmount"]
                    }
                    order_price_map[order_id] = price
                elif msg_type == "FILL":
                    if price in book_map:
                        if order_id in book_map[price]:
                            if msg.content["event"]["order"]["remainingQuoteTokenAmount"] == 0:
                                del book_map[price][order_id]
                                del order_price_map[order_id]
                            else:  # update the remaining amount of the order
                                book_map[price][order_id]["remainingBaseTokenAmount"] = \
                                    msg.content["event"]["order"]["remainingBaseTokenAmount"]
                                book_map[price][order_id]["remainingQuoteTokenAmount"] = \
                                    msg.content["event"]["order"]["remainingQuoteTokenAmount"]
                elif msg_type in ["CANCEL", "REMOVE"]:
                    if order_id not in order_price_map:
                        continue
                    price = order_price_map[order_id]
                    if order_id in book_map[price]:
                        del book_map[price][order_id]
                        del order_price_map[order_id]

            elif msg.type is OrderBookMessageType.SNAPSHOT:
                bids_map.clear()
                asks_map.clear()
                order_price_map.clear()
                for snapshot_orders, active_orders in [(msg.content["bids"], bids_map),
                                                       (msg.content["asks"], asks_map)]:
                    for order_entry in snapshot_orders:
                        order_id: str = order_entry["orderHash"]
                        price: Decimal = Decimal(order_entry["price"])
                        active_orders[price][order_id] = {
                            "orderHash": order_id,
                            "remainingBaseTokenAmount": order_entry["remainingBaseTokenAmount"],
                            "remainingQuoteTokenAmount": order_entry["remainingQuoteTokenAmount"]
                        }
                        order_price_map[order_id] = price

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
                total_amount = sum(float(item["remainingBaseTokenAmount"]) for item in orders.values())
            if total_amount == 0:
                self.assertTrue(float(price) not in post_bids.index,
                                f"{price} should not exist in the post_bids snapshot. {total_amount}")
            else:
                self.assertTrue(float(price) in post_bids.index,
                                f"{price} should exist in the post_bids snapshot. {total_amount}")
                self.assertAlmostEqual(float(total_amount), float(post_bids.loc[float(price)].amount),
                                       msg=f"total amount for {price} should be {total_amount}.")

        for price, orders in asks_map.items():
            total_amount: float = 0
            if len(orders) > 0:
                total_amount = sum(float(item["remainingBaseTokenAmount"]) for item in orders.values())
            if total_amount == 0:
                self.assertTrue(float(price) not in post_asks.index,
                                f"{price} should not exist in the post_asks snapshot.")
            else:
                self.assertTrue(float(price) in post_asks.index,
                                f"{price} should exist in the post_asks snapshot.")
                self.assertAlmostEqual(total_amount, float(post_asks.loc[float(price)].amount),
                                       msg=f"total amount for {price} should be {total_amount}.")

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
            self.assertAlmostEqual(float(trade_message.content["event"]["filledBaseTokenAmount"]),
                                   trade_event.amount)


if __name__ == "__main__":
    hummingsim.set_data_path(realpath(join(__file__, "../../data")))
    unittest.main()
