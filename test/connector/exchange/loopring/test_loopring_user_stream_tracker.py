#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.connector.exchange.loopring.loopring_api_order_book_data_source import LoopringAPIOrderBookDataSource
from hummingbot.connector.exchange.loopring.loopring_user_stream_tracker import LoopringUserStreamTracker
from hummingbot.connector.exchange.loopring.loopring_auth import LoopringAuth
import asyncio
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    # safe_gather,
)
import conf
# import json
import logging
import unittest

trading_pairs = ["ETH-USDT", "LRC-ETH", "LINK-ETH"]


class LoopringAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.loopring_auth = LoopringAuth(conf.loopring_api_key)
        cls.loopring_orderbook_data_source = LoopringAPIOrderBookDataSource(trading_pairs=trading_pairs)
        cls.user_stream_tracker: LoopringUserStreamTracker = LoopringUserStreamTracker(cls.loopring_orderbook_data_source, cls.loopring_auth)

    def run_async(self, task):
        return self.ev_loop.run_until_complete(task)

    async def _iter_user_event_queue(self):
        while True:
            try:
                yield await self.user_stream_tracker.user_stream.get()
            except asyncio.CancelledError:
                raise
            except Exception:
                raise

    async def _user_stream_event_listener(self):
        """ Wait for 5 events to be seen """
        count = 0
        async for event_message in self._iter_user_event_queue():
            logging.info(event_message)
            if count > 5:
                return
            count += 1

    def test_user_stream(self):
        safe_ensure_future(self.user_stream_tracker.start())
        # Wait process some msgs.
        self.ev_loop.run_until_complete(self._user_stream_event_listener())
        logging.info(self.user_stream_tracker.user_stream)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
