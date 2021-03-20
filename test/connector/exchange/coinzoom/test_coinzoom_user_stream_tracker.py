#!/usr/bin/env python

import sys
import asyncio
import logging
import unittest
import conf

from os.path import join, realpath
from hummingbot.connector.exchange.coinzoom.coinzoom_user_stream_tracker import CoinzoomUserStreamTracker
from hummingbot.connector.exchange.coinzoom.coinzoom_auth import CoinzoomAuth
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL


sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class CoinzoomUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.coinzoom_api_key
    api_secret = conf.coinzoom_secret_key
    api_username = conf.coinzoom_username

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.trading_pairs = ["BTC-USD"]
        cls.user_stream_tracker: CoinzoomUserStreamTracker = CoinzoomUserStreamTracker(
            coinzoom_auth=CoinzoomAuth(cls.api_key, cls.api_secret, cls.api_username),
            trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        print("Sleeping for 30s to gather some user stream messages.")
        self.ev_loop.run_until_complete(asyncio.sleep(30.0))
        print(self.user_stream_tracker.user_stream)
