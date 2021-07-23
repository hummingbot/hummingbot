#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))

from hummingbot.connector.exchange.dydx.dydx_api_order_book_data_source import DydxAPIOrderBookDataSource
from hummingbot.connector.exchange.dydx.dydx_user_stream_tracker import DydxUserStreamTracker
from hummingbot.connector.exchange.dydx.dydx_auth import DydxAuth
import asyncio
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    # safe_gather,
)
import conf
# import json
import logging
import unittest

trading_pairs = ["WETH-USDC", "WETH-DAI"]


class DydxAPIOrderBookDataSourceUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.dydx_auth = DydxAuth(conf.dydx_api_key)
        cls.dydx_orderbook_data_source = DydxAPIOrderBookDataSource(trading_pairs=trading_pairs)
        cls.user_stream_tracker: DydxUserStreamTracker = DydxUserStreamTracker(cls.dydx_orderbook_data_source, cls.dydx_auth)

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
