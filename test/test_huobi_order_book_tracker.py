#!/usr/bin/env python

from os.path import join, realpath
import sys
sys.path.insert(0, realpath(join(__file__, "../../")))

from hummingbot.market.huobi.huobi_order_book_tracker import HuobiOrderBookTracker
import asyncio
import logging
from typing import Dict, Optional
import unittest

from wings.order_book import OrderBook
from wings.order_book_tracker import (
    OrderBookTrackerDataSourceType
)


class HuobiOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[HuobiOrderBookTracker] = None
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: HuobiOrderBookTracker = HuobiOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API)
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
        self.ev_loop.run_until_complete(asyncio.sleep(10.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        btcusdt_book: OrderBook = order_books["btcusdt"]
        xrpusdt_book: OrderBook = order_books["xrpusdt"]
        # print(btcusdt_book.snapshot)
        # print(xrpusdt_book.snapshot)
        self.assertGreaterEqual(btcusdt_book.get_price_for_volume(True, 10).result_price,
                                btcusdt_book.get_price(True))
        self.assertLessEqual(btcusdt_book.get_price_for_volume(False, 10).result_price,
                             btcusdt_book.get_price(False))
        self.assertGreaterEqual(xrpusdt_book.get_price_for_volume(True, 10000).result_price,
                                xrpusdt_book.get_price(True))
        self.assertLessEqual(xrpusdt_book.get_price_for_volume(False, 10000).result_price,
                             xrpusdt_book.get_price(False))


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
