#!/usr/bin/env python

from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

import asyncio
import logging
import unittest
import conf

from os.path import join, realpath
from hummingbot.connector.exchange.digifinex.digifinex_user_stream_tracker import DigifinexUserStreamTracker
from hummingbot.connector.exchange.digifinex.digifinex_global import DigifinexGlobal
from hummingbot.core.utils.async_utils import safe_ensure_future

sys.path.insert(0, realpath(join(__file__, "../../../")))


class DigifinexUserStreamTrackerUnitTest(unittest.TestCase):
    api_key = conf.digifinex_api_key
    api_secret = conf.digifinex_secret_key

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls._global = DigifinexGlobal(cls.api_key, cls.api_secret)
        cls.trading_pairs = ["BTC-USDT"]
        cls.user_stream_tracker: DigifinexUserStreamTracker = DigifinexUserStreamTracker(
            cls._global, trading_pairs=cls.trading_pairs)
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
