#!/usr/bin/env python

import asyncio
import logging
import os
import sys
import unittest
from os.path import join, realpath

import conf
from hummingbot.connector.exchange.coinflex.coinflex_auth import CoinflexAuth
from hummingbot.connector.exchange.coinflex.coinflex_user_stream_tracker import CoinflexUserStreamTracker
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL

sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class CoinflexUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.coinflex_api_key
    api_secret = conf.coinflex_api_secret

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.trading_pairs = ["BTC-USD"]
        cls.user_stream_tracker: CoinflexUserStreamTracker = CoinflexUserStreamTracker(
            domain=os.getenv("COINFLEX_DOMAIN", "live"),
            auth=CoinflexAuth(api_key=cls.api_key,
                              secret_key=cls.api_secret,
                              time_provider=TimeSynchronizer()))
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        print("\nSleeping for 30s to gather some user stream messages.")
        self.ev_loop.run_until_complete(asyncio.sleep(30.0))
        print(self.user_stream_tracker.user_stream)
