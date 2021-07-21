#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import asyncio
import unittest

from typing import (
    Dict,
    Optional,
    List,
)

from hummingbot.connector.exchange.ndax.ndax_order_book_tracker import NdaxOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook


class NdaxOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[NdaxOrderBookTracker] = None

    trading_pairs: List[str] = [
        "BTC-CAD",
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: NdaxOrderBookTracker = NdaxOrderBookTracker(cls.trading_pairs)
        cls.order_book_tracker.start()
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    def test_tracker_integrity(self):
        # Allow 5 seconds for tracker to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        btc_cad: OrderBook = order_books["BTC-CAD"]
        self.assertIsNot(btc_cad.last_diff_uid, 0)
        self.assertGreaterEqual(btc_cad.get_price_for_volume(True, 10).result_price,
                                btc_cad.get_price(True))
        self.assertLessEqual(btc_cad.get_price_for_volume(False, 10).result_price,
                             btc_cad.get_price(False))
