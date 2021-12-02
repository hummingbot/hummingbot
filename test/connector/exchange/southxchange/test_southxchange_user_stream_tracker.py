#!/usr/bin/env python
import sys
import asyncio
import logging
import unittest
import conf

from os.path import join, realpath
from hummingbot.connector.exchange.southxchange.southxchange_user_stream_tracker import SouthxchangeUserStreamTracker
from hummingbot.connector.exchange.southxchange.southxchange_auth import SouthXchangeAuth
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL


sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class TestSouthXchangeUserStreamTracker(unittest.TestCase):
    api_key = conf.southxchange_api_key
    api_secret = conf.southxchange_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.southxchange_auth = SouthXchangeAuth(cls.api_key, cls.api_secret)
        cls.trading_pairs = ["BTC-USDT"]
        cls.user_stream_tracker: SouthxchangeUserStreamTracker = SouthxchangeUserStreamTracker(
            southxchange_auth=cls.southxchange_auth, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(120.0))
        print(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
