#!/usr/bin/env python

from os.path import join, realpath
import sys
sys.path.insert(0, realpath(join(__file__, "../../")))

import asyncio
import logging
import unittest
from typing import Dict, Optional

from hummingbot.market.bamboo_relay.bamboo_relay_order_book_tracker import BambooRelayOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTrackerDataSourceType
)


class BambooRelayOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[BambooRelayOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: BambooRelayOrderBookTracker = BambooRelayOrderBookTracker(
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
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        weth_dai_book: OrderBook = order_books["WETH-DAI"]
        zrx_weth_book: OrderBook = order_books["ZRX-WETH"]
        # print(weth_dai_book.snapshot)
        # print(zrx_weth_book.snapshot)
        self.assertGreaterEqual(weth_dai_book.get_price_for_volume(True, 10).result_price,
                                weth_dai_book.get_price(True))
        self.assertLessEqual(weth_dai_book.get_price_for_volume(False, 10).result_price,
                             weth_dai_book.get_price(False))
        self.assertGreaterEqual(zrx_weth_book.get_price_for_volume(True, 10).result_price,
                                zrx_weth_book.get_price(True))
        self.assertLessEqual(zrx_weth_book.get_price_for_volume(False, 10).result_price,
                             zrx_weth_book.get_price(False))


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
