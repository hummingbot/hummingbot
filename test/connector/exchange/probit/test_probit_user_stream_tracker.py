#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../")))

import asyncio
import conf
import logging
import unittest


from hummingbot.connector.exchange.probit.probit_user_stream_tracker import ProbitUserStreamTracker
from hummingbot.connector.exchange.probit.probit_auth import ProbitAuth
from hummingbot.core.utils.async_utils import safe_ensure_future


class ProbitUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.probit_api_key
    api_secret = conf.probit_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.probit_auth = ProbitAuth(cls.api_key, cls.api_secret)
        cls.trading_pairs = ["PROB-USDT"]
        cls.user_stream_tracker: ProbitUserStreamTracker = ProbitUserStreamTracker(
            probit_auth=cls.probit_auth, trading_pairs=cls.trading_pairs)
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
