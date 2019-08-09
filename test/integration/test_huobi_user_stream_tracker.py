#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import logging
import unittest
import conf
from typing import (
    Optional
)
from hummingbot.market.huobi.huobi_market import HuobiAuth
from hummingbot.market.huobi.huobi_user_stream_tracker import HuobiUserStreamTracker


class HuobiUserStreamTrackerUnitTest(unittest.TestCase):
    user_stream_tracker: Optional[HuobiUserStreamTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.huobi_auth = HuobiAuth(conf.huobi_api_key,
                                   conf.huobi_secret_key)
        cls.symbols = ["ethusdt"]
        cls.user_stream_tracker: HuobiUserStreamTracker = HuobiUserStreamTracker(
            huobi_auth=cls.huobi_auth, symbols=cls.symbols)
        cls.user_stream_tracker_task: asyncio.Task = asyncio.ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(60.0))
        print(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
