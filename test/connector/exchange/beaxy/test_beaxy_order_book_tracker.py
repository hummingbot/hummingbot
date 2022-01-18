#!/usr/bin/env python
from os.path import (
    join,
    realpath
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    OrderBookEvent
)
import asyncio
import logging
import unittest
from typing import Dict, Optional, List

from hummingbot.connector.exchange.beaxy.beaxy_order_book_tracker import BeaxyOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSource
from hummingbot.core.utils.async_utils import safe_ensure_future, safe_gather


class BeaxyOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[BeaxyOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "BXY-BTC",
    ]

    integrity_test_max_volume = 5  # Max volume in asks and bids for the book to be ready for tests
    daily_volume = 2500  # Approximate total daily volume in BTC for this exchange for sanity test
    book_enties = 5  # Number of asks and bids (each) for the book to be ready for tests

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: BeaxyOrderBookTracker = BeaxyOrderBookTracker(cls.trading_pairs)
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        print("Waiting for order book to fill...")
        while True:
            book_present = cls.trading_pairs[0] in cls.order_book_tracker.order_books
            enough_asks = False
            enough_bids = False
            enough_ask_rows = False
            enough_bid_rows = False
            if book_present:
                ask_volume = sum(i.amount for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].ask_entries())
                ask_count = sum(1 for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].ask_entries())

                bid_volume = sum(i.amount for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].bid_entries())
                bid_count = sum(1 for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].bid_entries())

                enough_asks = ask_volume >= cls.integrity_test_max_volume
                enough_bids = bid_volume >= cls.integrity_test_max_volume

                enough_ask_rows = ask_count >= cls.book_enties
                enough_bid_rows = bid_count >= cls.book_enties

                print("Bid volume in book: %f (in %d bids), ask volume in book: %f (in %d asks)" % (bid_volume, bid_count, ask_volume, ask_count))

            if book_present and enough_asks and enough_bids and enough_ask_rows and enough_bid_rows:
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

    def test_tracker_integrity(self):
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        sut_book: OrderBook = order_books[self.trading_pairs[0]]

        self.assertGreater(sut_book.get_price(True), sut_book.get_price(False))

        self.assertGreaterEqual(sut_book.get_price_for_volume(True, self.integrity_test_max_volume).result_price,
                                sut_book.get_price(True))

        self.assertLessEqual(sut_book.get_price_for_volume(False, self.integrity_test_max_volume).result_price,
                             sut_book.get_price(False))

        previous_price = sys.float_info.max
        for bid_row in sut_book.bid_entries():
            self.assertTrue(previous_price >= bid_row.price)
            previous_price = bid_row.price

        previous_price = 0
        for ask_row in sut_book.ask_entries():
            self.assertTrue(previous_price <= ask_row.price)
            previous_price = ask_row.price

    def test_order_book_data_source(self):
        self.assertTrue(isinstance(self.order_book_tracker.data_source, OrderBookTrackerDataSource))

    def test_get_trading_pairs(self):
        [trading_pairs] = self.run_parallel(self.order_book_tracker.data_source.get_trading_pairs())
        self.assertGreater(len(trading_pairs), 0)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
