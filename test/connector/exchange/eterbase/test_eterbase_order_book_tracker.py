#!/usr/bin/env python
import math
from os.path import (
    join,
    realpath
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    OrderBookTradeEvent,
    TradeType,
    OrderBookEvent
)
import asyncio
import logging
import unittest
from datetime import datetime
from decimal import Decimal
from typing import (
    Dict,
    Optional,
    List,
)
from hummingbot.connector.exchange.eterbase.eterbase_order_book_tracker import EterbaseOrderBookTracker
from hummingbot.connector.exchange.eterbase.eterbase_api_order_book_data_source import EterbaseAPIOrderBookDataSource
from hummingbot.connector.exchange.eterbase.eterbase_order_book import EterbaseOrderBook
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)


class EterbaseOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[EterbaseOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "ETHEUR"
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: EterbaseOrderBookTracker = EterbaseOrderBookTracker(
            trading_pairs=cls.trading_pairs)
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    async def run_parallel_async(self, *tasks, timeout=None):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        timer = 0
        while not future.done():
            if timeout and timer > timeout:
                raise Exception("Time out running parallel async task in tests.")
            timer += 1
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def setUp(self):
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    @unittest.skip
    def test_order_book_trade_event_emission(self):
        """
        Test if order book tracker is able to retrieve order book trade message from exchange and
        emit order book trade events after correctly parsing the trade messages
        """
        self.run_parallel(self.event_logger.wait_for(OrderBookTradeEvent))
        for ob_trade_event in self.event_logger.event_log:
            self.assertTrue(type(ob_trade_event) == OrderBookTradeEvent)
            self.assertTrue(ob_trade_event.trading_pair in self.trading_pairs)
            self.assertTrue(type(ob_trade_event.timestamp) == float)
            self.assertTrue(type(ob_trade_event.amount) == float)
            self.assertTrue(type(ob_trade_event.price) == float)
            self.assertTrue(type(ob_trade_event.type) == TradeType)
            self.assertTrue(math.ceil(math.log10(ob_trade_event.timestamp)) == 10)
            self.assertTrue(ob_trade_event.amount > 0)
            self.assertTrue(ob_trade_event.price > 0)

    def test_tracker_integrity(self):
        # Wait 5 seconds to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books["ETHEUR"]

        self.assertGreaterEqual(test_order_book.get_price_for_volume(True, 10).result_price,
                                test_order_book.get_price(True))
        self.assertLessEqual(test_order_book.get_price_for_volume(False, 10).result_price,
                             test_order_book.get_price(False))

        test_active_order_tracker = self.order_book_tracker._active_order_trackers["ETHEUR"]
        self.assertTrue(len(test_active_order_tracker.active_asks) > 0)
        self.assertTrue(len(test_active_order_tracker.active_bids) > 0)
        for order_book in self.order_book_tracker.order_books.values():
            print(f"last_trade_price: {order_book.last_trade_price}")
            self.assertFalse(math.isnan(order_book.last_trade_price))

    def test_order_book_data_source(self):
        self.assertTrue(isinstance(self.order_book_tracker.data_source, OrderBookTrackerDataSource))

    def test_diff_msg_get_added_to_order_book(self):
        test_active_order_tracker = self.order_book_tracker._active_order_trackers["ETHEUR"]

        price = "200"
        order_id = "test_order_id"
        market_id = 51
        size = "1.50"
        remaining_size = "1.00"

        # Test open message diff
        raw_open_message = {
            "type": "o_placed",
            "timestamp": datetime.now().timestamp() * 1000,
            "marketId": market_id,
            "orderId": order_id,
            "limitPrice": price,
            "qty": size,
            "oType": 2,
            "side": 1
        }
        open_message = EterbaseOrderBook.diff_message_from_exchange(raw_open_message)
        self.order_book_tracker._order_book_diff_stream.put_nowait(open_message)
        self.run_parallel(asyncio.sleep(5))

        test_order_book_row = test_active_order_tracker.active_bids[Decimal(price)]
        self.assertEqual(test_order_book_row[order_id]["remaining_size"], size)

        # Test match message diff
        match_size = "0.50"
        raw_match_message = {
            "type": "o_fill",
            "tradeId": 10,
            "orderId": order_id,
            "timestamp": datetime.now().timestamp() * 1000,
            "marketId": market_id,
            "qty": match_size,
            "remainingQty": remaining_size,
            "price": price,
            "side": 1
        }
        match_message = EterbaseOrderBook.diff_message_from_exchange(raw_match_message)

        self.order_book_tracker._order_book_diff_stream.put_nowait(match_message)
        self.run_parallel(asyncio.sleep(5))

        test_order_book_row = test_active_order_tracker.active_bids[Decimal(price)]
        self.assertEqual(Decimal(test_order_book_row[order_id]["remaining_size"]),
                         Decimal(remaining_size))

        # Test done message diff
        raw_done_message = {
            "type": "o_closed",
            "timestamp": datetime.now().timestamp() * 1000,
            "marketId": market_id,
            "limitPrice": price,
            "orderId": order_id,
            "reason": "FILLED",
            "qty": match_size,
            "remainingQty": "1.00",
            "side": 1
        }
        done_message = EterbaseOrderBook.diff_message_from_exchange(raw_done_message)

        self.order_book_tracker._order_book_diff_stream.put_nowait(done_message)
        self.run_parallel(asyncio.sleep(5))

        self.assertTrue(Decimal(price) not in test_active_order_tracker.active_bids)

    def test_api_get_last_traded_prices(self):
        prices = self.ev_loop.run_until_complete(
            EterbaseAPIOrderBookDataSource.get_last_traded_prices(["BTCEUR", "LTCEUR"]))
        for key, value in prices.items():
            print(f"{key} last_trade_price: {value}")
        self.assertGreater(prices["BTCEUR"], 1000)
        self.assertLess(prices["LTCEUR"], 1000)


def main():
    logging.basicConfig(level=logging.DEBUG)
    unittest.main()


if __name__ == "__main__":
    main()
