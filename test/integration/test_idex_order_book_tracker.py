#!/usr/bin/env python
import math
import asyncio
import logging
import time
import unittest

from os.path import join, realpath
import sys

from hummingbot.connector.exchange.idex.idex_api_order_book_data_source import IdexAPIOrderBookDataSource
from hummingbot.connector.exchange.idex.idex_order_book_tracker import IdexOrderBookTracker
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType

sys.path.insert(0, realpath(join(__file__, "../../../")))

from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent, TradeType

from typing import Dict, Optional, List

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)


# API_MOCK_ENABLED = conf.mock_api_enabled is not None and conf.mock_api_enabled.lower() in ['true', 'yes', '1']
# API_KEY = "XXX" if API_MOCK_ENABLED else conf.idex_api_key
# API_SECRET = "YYY" if API_MOCK_ENABLED else conf.idex_api_secret


class IdexOrderBookTrackerUnitTest(unittest.TestCase):

    order_book_tracker: Optional[IdexOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "DIL-ETH",
        "PIP-ETH"
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: IdexOrderBookTracker = IdexOrderBookTracker(
            trading_pairs=cls.trading_pairs
        )
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls._publish_event()
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        while True:
            if len(cls.order_book_tracker.order_books) > 0:
                return
            await asyncio.sleep(1)

    @classmethod
    def _publish_event(cls):
        order_book_message = OrderBookMessage(OrderBookMessageType.TRADE, {
            "trading_pair": "DIL-ETH",
            "update_id": "123",
            "bids": [
                [1, 1]
            ],
            "asks": [
                [1, 1]
            ]
        }, timestamp=time.time())
        cls.ev_loop.run_until_complete(cls.order_book_tracker._order_book_trade_stream.put(order_book_message))

    async def run_parallel_async(self, *tasks):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        while not future.done():
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def setUp(self):
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    def test_order_book_trade_event_emission(self):
        self.run_parallel(self.event_logger.wait_for(OrderBookTradeEvent))
        for ob_trade_event in self.event_logger.event_log:
            self.assertTrue(type(ob_trade_event) == OrderBookTradeEvent)
            self.assertTrue(ob_trade_event.trading_pair in self.trading_pairs)
            self.assertTrue(type(ob_trade_event.timestamp) == float)
            self.assertTrue(type(ob_trade_event.amount) == float)
            self.assertTrue(type(ob_trade_event.price) == float)
            self.assertTrue(type(ob_trade_event.type) == TradeType)
            self.assertTrue(math.ceil(math.log10(ob_trade_event.timestamp)) == 10)
            self.assertTrue(ob_trade_event.amount > 0)
            self.assertTrue(ob_trade_event.price > 0)

    def test_tracker_integrity(self):
        # Wait 5 seconds to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(30.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        dil_eth: OrderBook = order_books["DIL-ETH"]
        self.assertIsNot(dil_eth.last_diff_uid, 0)
        self.assertGreaterEqual(dil_eth.get_price_for_volume(True, 10).result_price,
                                dil_eth.get_price(True))
        self.assertLessEqual(dil_eth.get_price_for_volume(False, 10).result_price,
                             dil_eth.get_price(False))

    def test_api_get_last_traded_prices(self):
        """
        # TODO: Fix 429 error
        """
        prices = self.ev_loop.run_until_complete(
            IdexAPIOrderBookDataSource.get_last_traded_prices(['DIL-ETH', 'PIP-ETH', 'CUR-ETH'])
        )

        for key, value in prices.items():
            print(f"{key} last_trade_price: {value}")

        self.assertGreater(prices["DIL-ETH"], 0.05)
        self.assertLess(prices["PIP-ETH"], 1)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
