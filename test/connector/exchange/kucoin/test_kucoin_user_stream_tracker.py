#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.connector.exchange.kucoin.kucoin_user_stream_tracker import KucoinUserStreamTracker
from hummingbot.connector.exchange.kucoin.kucoin_auth import KucoinAuth
from hummingbot.core.utils.async_utils import safe_ensure_future


from hummingbot.connector.exchange.kucoin.kucoin_order_book_tracker import KucoinOrderBookTracker
import asyncio
import logging
import conf
from typing import Optional
import unittest

# logging.basicConfig(level=logging.DEBUG)


class KucoinOrderBookTrackerUnitTest(unittest.TestCase):

    order_book_tracker: Optional[KucoinOrderBookTracker] = None

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
