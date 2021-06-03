#!/usr/bin/env python

from os.path import join, realpath
import sys

import conf
from hummingbot.connector.exchange.bittrex.bittrex_auth import BittrexAuth

from hummingbot.connector.exchange.bittrex.bittrex_user_stream_tracker import BittrexUserStreamTracker

from hummingbot.connector.exchange.bittrex.bittrex_order_book_tracker import BittrexOrderBookTracker
import asyncio
import logging
from typing import Optional
import unittest

sys.path.insert(0, realpath(join(__file__, "../../../../../")))

logging.basicConfig(level=logging.DEBUG)


class BittrexUserStreamTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[BittrexOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.bittrex_auth = BittrexAuth(conf.bittrex_api_key,
                                       conf.bittrex_secret_key)
        cls.trading_pairs = ["LTC-ETH"]  # Using V3 convention since OrderBook is built using V3
        cls.user_stream_tracker: BittrexUserStreamTracker = BittrexUserStreamTracker(
            bittrex_auth=cls.bittrex_auth, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
