#!/usr/bin/env python
import sys
import asyncio
import logging
import unittest
import conf

from os.path import join, realpath
from hummingbot.connector.exchange.bitmax.bitmax_user_stream_tracker import BitmaxUserStreamTracker
from hummingbot.connector.exchange.bitmax.bitmax_auth import BitmaxAuth
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL


sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class BitmaxUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.bitmax_api_key
    api_secret = conf.bitmax_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.bitmax_auth = BitmaxAuth(cls.api_key, cls.api_secret)
        cls.trading_pairs = ["BTC-USDT"]
        cls.user_stream_tracker: BitmaxUserStreamTracker = BitmaxUserStreamTracker(
            bitmax_auth=cls.bitmax_auth, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)
