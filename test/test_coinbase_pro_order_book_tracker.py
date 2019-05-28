#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../")))

import asyncio
import logging
import unittest
from typing import (
    Dict,
    Optional
)
from hummingbot.market.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType

test_symbol = "XLM-USD"


class CoinbaseProOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[CoinbaseProOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: CoinbaseProOrderBookTracker = CoinbaseProOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API,
            symbols=[test_symbol])
        cls.order_book_tracker_task: asyncio.Task = asyncio.ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    def test_tracker_integrity(self):
        # Wait 5 seconds to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books[test_symbol]
        # print("test_order_book")
        # print(test_order_book.snapshot)
        self.assertGreaterEqual(test_order_book.get_price_for_volume(True, 10).result_price,
                                test_order_book.get_price(True))
        self.assertLessEqual(test_order_book.get_price_for_volume(False, 10).result_price,
                             test_order_book.get_price(False))

        test_active_order_tracker = self.order_book_tracker._active_order_trackers[test_symbol]
        self.assertTrue(len(test_active_order_tracker.active_asks) > 0)
        self.assertTrue(len(test_active_order_tracker.active_bids) > 0)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
