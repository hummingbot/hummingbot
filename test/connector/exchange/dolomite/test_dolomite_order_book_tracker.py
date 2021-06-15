#!/usr/bin/env python

from os.path import join, realpath
import sys

import asyncio
import logging
import unittest
from typing import Dict, Optional

from hummingbot.connector.exchange.dolomite.dolomite_order_book_tracker import DolomiteOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import OrderBookTrackerDataSourceType

sys.path.insert(0, realpath(join(__file__, "../../../../../")))

TESTNET_API_REST_ENDPOINT = "https://exchange-api-test.dolomite.io"
TESTNET_WS_ENDPOINT = "wss://exchange-api-test.dolomite.io/ws-connect"


class DolomiteOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[DolomiteOrderBookTracker] = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: DolomiteOrderBookTracker = DolomiteOrderBookTracker(
            data_source_type=OrderBookTrackerDataSourceType.EXCHANGE_API,
            rest_api_url=TESTNET_API_REST_ENDPOINT,
            websocket_url=TESTNET_WS_ENDPOINT,
        )
        cls.order_book_tracker_task: asyncio.Task = asyncio.ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                print("Initialized real-time order books.")
                return
            await asyncio.sleep(1)

    def test_tracker_integrity(self):
        # Wait 5 seconds to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        weth_dai_book: OrderBook = order_books["WETH-DAI"]
        self.assertGreaterEqual(
            weth_dai_book.get_price_for_volume(True, 0.1).result_price, weth_dai_book.get_price(True)
        )


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
