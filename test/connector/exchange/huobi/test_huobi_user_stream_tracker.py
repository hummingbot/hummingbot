#!/usr/bin/env python

from os.path import join, realpath
import sys

import asyncio
import conf

import logging
import unittest

from typing import Optional

from hummingbot.connector.exchange.huobi.huobi_auth import HuobiAuth
from hummingbot.connector.exchange.huobi.huobi_user_stream_tracker import HuobiUserStreamTracker

sys.path.insert(0, realpath(join(__file__, "../../../../../")))

logging.basicConfig(level=logging.DEBUG)


class HuobiUserStreamTrackerUniTest(unittest.TestCase):
    order_book_tracker: Optional[HuobiUserStreamTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.huobi_auth = HuobiAuth(conf.huobi_api_key,
                                   conf.huobi_secret_key)
        cls.trading_pairs = ["btcusdt"]
        cls.user_stream_tracker: HuobiUserStreamTracker = HuobiUserStreamTracker(
            huobi_auth=cls.huobi_auth,
            trading_pairs=cls.trading_pairs
        )
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait for some messages to be queued.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
