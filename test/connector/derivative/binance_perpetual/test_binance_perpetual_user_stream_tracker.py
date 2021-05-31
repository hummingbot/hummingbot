#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import asyncio
import logging
from typing import Optional
import unittest

from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_tracker import BinancePerpetualUserStreamTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_order_book_tracker import BinancePerpetualOrderBookTracker

logging.basicConfig(level=logging.DEBUG)


class BinancePerpetualOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[BinancePerpetualOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.user_stream_tracker: BinancePerpetualUserStreamTracker = BinancePerpetualUserStreamTracker(api_key="", base_url="https://testnet.binancefuture.com", stream_url="wss://stream.binancefuture.com")
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
