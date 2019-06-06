#!/usr/bin/env python

from os.path import join, realpath
import sys
sys.path.insert(0, realpath(join(__file__, "../../")))

import asyncio
import logging
import unittest
from typing import (
  Dict,
  Optional
)

from hummingbot.market.idex.idex_order_book_tracker import IDEXOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType


TEST_PAIR_1 = "ETH_FXC"
TEST_PAIR_2 = "ETH_FTM"
TEST_PAIR_3 = "ETH_LINK"
TEST_PAIRS = [TEST_PAIR_1]


class IDEXOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[IDEXOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: IDEXOrderBookTracker = IDEXOrderBookTracker(
            OrderBookTrackerDataSourceType.EXCHANGE_API,
            symbols=TEST_PAIRS
        )
        cls.order_book_tracker_task: asyncio.Task = asyncio.ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1000)

    def test_tracker_integrity(self):
        # Wait 5 seconds to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(10.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        zrx_weth_book: OrderBook = order_books[TEST_PAIR_1]
        # weth_tusd_book: OrderBook = order_books["ETH_QNT"]
        print("zrx_weth_book")
        print(zrx_weth_book.snapshot)
        print("weth_tusd_book")
        print(weth_tusd_book.snapshot)
        self.assertGreaterEqual(zrx_weth_book.get_price_for_volume(True, 10), zrx_weth_book.get_price(True))
        self.assertLessEqual(zrx_weth_book.get_price_for_volume(False, 10), zrx_weth_book.get_price(False))
        # self.assertGreaterEqual(weth_tusd_book.get_price_for_volume(True, 10), weth_tusd_book.get_price(True))
        # self.assertLessEqual(weth_tusd_book.get_price_for_volume(False, 10), weth_tusd_book.get_price(False))


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
