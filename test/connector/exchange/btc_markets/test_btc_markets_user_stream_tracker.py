#!/usr/bin/env python

import asyncio
import logging
import sys
import unittest
from os.path import join, realpath

import conf
from hummingbot.connector.exchange.btc_markets.btc_markets_auth import BtcMarketsAuth
from hummingbot.connector.exchange.btc_markets.btc_markets_user_stream_tracker import BtcMarketsUserStreamTracker
from hummingbot.core.utils.async_utils import safe_ensure_future

sys.path.insert(0, realpath(join(__file__, "../../../")))


class BtcMarketsUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.btc_markets_api_key
    secret_key = conf.btc_markets_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.btc_markets_auth = BtcMarketsAuth(cls.api_key, cls.secret_key)
        cls.trading_pairs = ["BTC-AUD"]
        cls.user_stream_tracker: BtcMarketsUserStreamTracker = BtcMarketsUserStreamTracker(
            btc_markets_auth=cls.btc_markets_auth, trading_pairs=cls.trading_pairs)
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    def test_user_stream(self):
        # Wait process some msgs.
        self.ev_loop.run_until_complete(asyncio.sleep(20.0))
        print(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
