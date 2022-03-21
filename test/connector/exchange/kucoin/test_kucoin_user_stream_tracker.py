#!/usr/bin/env python

import asyncio
import logging
import sys
import unittest
from os.path import join, realpath

import conf
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.connector.exchange.kucoin.kucoin_user_stream_tracker import KucoinUserStreamTracker
from hummingbot.core.utils.async_utils import safe_ensure_future

sys.path.insert(0, realpath(join(__file__, "../../../../../")))


class KucoinOrderBookTrackerUnitTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.kucoin_auth = KucoinAuth(conf.kucoin_api_key, conf.kucoin_passphrase, conf.kucoin_secret_key)
        cls.user_stream_tracker: KucoinUserStreamTracker = KucoinUserStreamTracker(kucoin_auth=cls.kucoin_auth)
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
