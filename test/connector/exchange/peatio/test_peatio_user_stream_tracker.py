#!/usr/bin/env python

from os.path import join, realpath
import sys

import asyncio
import conf

import logging
import unittest

from typing import Optional

from hummingbot.connector.exchange.peatio.peatio_auth import PeatioAuth
from hummingbot.connector.exchange.peatio.peatio_user_stream_tracker import PeatioUserStreamTracker

sys.path.insert(0, realpath(join(__file__, "../../../../../")))

logging.basicConfig(level=logging.DEBUG)


class PeatioUserStreamTrackerUniTest(unittest.TestCase):
    order_book_tracker: Optional[PeatioUserStreamTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.peatio_auth = PeatioAuth(conf.peatio_access_key, conf.peatio_secret_key)
        cls.trading_pairs = ["btc_usdterc20"]
        cls.user_stream_tracker: PeatioUserStreamTracker = PeatioUserStreamTracker(
            peatio_auth=cls.peatio_auth,
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
