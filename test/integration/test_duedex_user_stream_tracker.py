#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import conf

import logging
import unittest

from typing import Optional

from hummingbot.connector.exchange.duedex.duedex_auth import DuedexAuth
from hummingbot.connector.exchange.duedex.duedex_user_stream_tracker import DuedexUserStreamTracker


logging.basicConfig(level=logging.DEBUG)


class DuedexUserStreamTrackerUniTest(unittest.TestCase):
    order_book_tracker: Optional[DuedexUserStreamTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.duedex_auth = DuedexAuth(conf.duedex_api_key,
                                     conf.duedex_secret_key)
        cls.trading_pairs = ["btcusdt"]
        cls.user_stream_tracker: DuedexUserStreamTracker = DuedexUserStreamTracker(
            duedex_auth=cls.duedex_auth,
            trading_pairs=cls.trading_pairs
        )
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait for some messages to be queued.
        self.ev_loop.run_until_complete(asyncio.sleep(60.0))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
