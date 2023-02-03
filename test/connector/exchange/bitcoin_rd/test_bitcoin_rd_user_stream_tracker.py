#!/usr/bin/env python
import sys
import asyncio
import logging
import unittest
import conf

from os.path import join, realpath
from hummingbot.connector.exchange.bitcoin_rd.bitcoin_rd_user_stream_tracker import BitcoinRDUserStreamTracker
from hummingbot.connector.exchange.bitcoin_rd.bitcoin_rd_auth import BitcoinRDAuth
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL
from hummingbot.connector.exchange.bitcoin_rd import bitcoin_rd_constants as CONSTANTS


sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class BitcoinRDUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.bitcoin_rd_api_key
    api_secret = conf.bitcoin_rd_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        cls.bitcoin_rd_auth = BitcoinRDAuth(cls.api_key, cls.api_secret)
        cls.trading_pairs = ["BTC-USDT"]
        cls.user_stream_tracker: BitcoinRDUserStreamTracker = BitcoinRDUserStreamTracker(
            cls.throttler, bitcoin_rd_auth=cls.bitcoin_rd_auth, trading_pairs=cls.trading_pairs
        )
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)
