#!/usr/bin/env python
from os.path import join, realpath
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
import conf
from hummingbot.connector.exchange.wazirx.wazirx_api_order_book_data_source import WazirxAPIOrderBookDataSource
from hummingbot.connector.exchange.wazirx.wazirx_user_stream_tracker import WazirxUserStreamTracker
from hummingbot.connector.exchange.wazirx.wazirx_auth import WazirxAuth
import asyncio
from hummingbot.core.utils.async_utils import safe_ensure_future

import logging
import unittest

trading_pairs = ["BTC-INR", "ZRX-INR"]


class WazirxUserStreamTrackerUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        api_key = conf.wazirx_api_key
        secret_key = conf.wazirx_secret_key
        cls.wazirx_auth = WazirxAuth(api_key, secret_key)
        cls.wazirx_orderbook_data_source = WazirxAPIOrderBookDataSource(trading_pairs=trading_pairs)
        cls.user_stream_tracker: WazirxUserStreamTracker = WazirxUserStreamTracker(cls.wazirx_auth, trading_pairs)

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
