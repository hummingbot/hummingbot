#!/usr/bin/env python
import asyncio
import conf
import logging
import unittest
from os.path import join, realpath
import sys

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange.liquid.liquid_auth import LiquidAuth
from hummingbot.connector.exchange.liquid.liquid_user_stream_tracker import LiquidUserStreamTracker

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=logging.DEBUG)


class LiquidOrderBookTrackerUnitTest(unittest.TestCase):

    trading_pairs = [
        'ETH-USD'
    ]

    @classmethod
    def setUpClass(cls):
        cls._liquid_auth: LiquidAuth = LiquidAuth(
            api_key=conf.liquid_api_key,
            secret_key=conf.liquid_secret_key)
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.user_stream_tracker: LiquidUserStreamTracker = LiquidUserStreamTracker(
            liquid_auth=cls._liquid_auth,
            trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
