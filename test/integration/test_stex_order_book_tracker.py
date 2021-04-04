#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.connector.exchange.stex.stex_order_book_tracker import StexOrderBookTracker
from hummingbot.connector.exchange.stex.stex_api_order_book_data_source import StexAPIOrderBookDataSource
import asyncio
import logging
import unittest


class StexOrderBookTrackerUnitTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: StexOrderBookTracker = StexOrderBookTracker(trading_pairs=["ABS-BTC", "ABET-BTC", "ACRYL-BTC"])
        cls.order_book_tracker.start()
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    def test_data_source(self):
        self.assertIsInstance(self.order_book_tracker.data_source, StexAPIOrderBookDataSource)

    def test_name(self):
        self.assertEqual(self.order_book_tracker.exchange_name, "stex")

    def test_start_stop(self):
        self.assertTrue(asyncio.isfuture(self.order_book_tracker._order_book_snapshot_router_task))
        self.order_book_tracker.stop()
        self.assertIsNone(self.order_book_tracker._order_book_snapshot_router_task)
        self.order_book_tracker.start()


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
