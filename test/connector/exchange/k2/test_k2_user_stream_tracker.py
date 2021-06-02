#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import conf
import logging
import unittest


from hummingbot.connector.exchange.k2.k2_user_stream_tracker import K2UserStreamTracker
from hummingbot.connector.exchange.k2.k2_auth import K2Auth
from hummingbot.core.utils.async_utils import safe_ensure_future


class K2UserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.k2_api_key
    api_secret = conf.k2_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.k2_auth = K2Auth(cls.api_key, cls.api_secret)
        cls.trading_pairs = ["ETH-USD"]
        cls.user_stream_tracker: K2UserStreamTracker = K2UserStreamTracker(
            k2_auth=cls.k2_auth, trading_pairs=cls.trading_pairs)
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
