#!/usr/bin/env python
import os
from os.path import join, realpath
import sys

from hummingbot.connector.exchange.idex.idex_auth import IdexAuth

sys.path.insert(0, realpath(join(__file__, "../../../")))
import asyncio
import logging
import unittest

from typing import Optional

from hummingbot.connector.exchange.idex.idex_user_stream_tracker import IdexUserStreamTracker
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.connector.exchange.idex.idex_order_book_tracker import IdexOrderBookTracker


logging.basicConfig(level=logging.DEBUG)


class IdexOrderBookTrackerUnitTest(unittest.TestCase):

    order_book_tracker: Optional[IdexOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.user_stream_tracker: IdexUserStreamTracker = IdexUserStreamTracker(
            idex_auth=IdexAuth(
                api_key=os.getenv("IDEX_API_KEY"),
                secret_key=os.getenv("IDEX_SECRET_KEY")
            )
        )
        cls.user_stream_tracker_task: asyncio.Task = safe_ensure_future(cls.user_stream_tracker.start())

    # @unittest.skip
    def test_user_stream_manually(self):
        """
        This test should be run before market functions like buy and sell are implemented.
        Developer needs to manually trigger those actions in order for the messages to show up in the user stream.
        """
        self.ev_loop.run_until_complete(asyncio.sleep(10.0))
        print(self.user_stream_tracker.user_stream)


def main():
    unittest.main()


if __name__ == "__main__":
    main()
