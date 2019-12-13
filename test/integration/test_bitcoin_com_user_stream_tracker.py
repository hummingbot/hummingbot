#!/usr/bin/env python

import sys
import asyncio
import logging
import unittest
import conf

from os.path import join, realpath
from typing import (
    Optional
)
from hummingbot.market.bitcoin_com.bitcoin_com_user_stream_tracker import BitcoinComUserStreamTracker
from hummingbot.market.bitcoin_com.bitcoin_com_auth import BitcoinComAuth
from hummingbot.core.utils.async_utils import safe_ensure_future

sys.path.insert(0, realpath(join(__file__, "../../../")))


class BitcoinComUserStreamTrackerUnitTest(unittest.TestCase):
    user_stream_tracker: Optional[BitcoinComUserStreamTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.bitcoin_com_auth = BitcoinComAuth(conf.bitcoin_com_api_key, conf.bitcoin_com_secret_key)
        cls.trading_pairs = ["ETHBTC"]
        cls.user_stream_tracker: BitcoinComUserStreamTracker = BitcoinComUserStreamTracker(
            bitcoin_com_auth=cls.bitcoin_com_auth, trading_pairs=cls.trading_pairs)
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
