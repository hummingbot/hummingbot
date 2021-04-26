#!/usr/bin/env python
import sys
import math
import time
import asyncio
import logging
import unittest
from async_timeout import timeout
from os.path import join, realpath
from typing import Dict, Optional, List
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent, TradeType
from hummingbot.connector.exchange.coinzoom.coinzoom_order_book_tracker import CoinzoomOrderBookTracker
from hummingbot.connector.exchange.coinzoom.coinzoom_api_order_book_data_source import CoinzoomAPIOrderBookDataSource
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.logger.struct_logger import METRICS_LOG_LEVEL


sys.path.insert(0, realpath(join(__file__, "../../../../../")))
logging.basicConfig(level=METRICS_LOG_LEVEL)


class CoinzoomOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[CoinzoomOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "BTC-USD",
        "ETH-USD",
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: CoinzoomOrderBookTracker = CoinzoomOrderBookTracker(cls.trading_pairs)
        cls.order_book_tracker.start()
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        async with timeout(20):
            while True:
                if len(cls.order_book_tracker.order_books) > 0:
                    print("Initialized real-time order books.")
                    return
                await asyncio.sleep(1)

    async def run_parallel_async(self, *tasks, timeout=None):
        future: asyncio.Future = asyncio.ensure_future(asyncio.gather(*tasks))
        timer = 0
        while not future.done():
            if timeout and timer > timeout:
                raise Exception("Timeout running parallel async tasks in tests")
            timer += 1
            now = time.time()
            _next_iteration = now // 1.0 + 1  # noqa: F841
            await asyncio.sleep(1.0)
        return future.result()

    def run_parallel(self, *tasks):
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks, timeout=60))

    def setUp(self):
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    def test_order_book_trade_event_emission(self):
        """
        Tests if the order book tracker is able to retrieve order book trade message from exchange and emit order book
        trade events after correctly parsing the trade messages
        """
        self.run_parallel(self.event_logger.wait_for(OrderBookTradeEvent))
        for ob_trade_event in self.event_logger.event_log:
            self.assertTrue(type(ob_trade_event) == OrderBookTradeEvent)
            self.assertTrue(ob_trade_event.trading_pair in self.trading_pairs)
            self.assertTrue(type(ob_trade_event.timestamp) in [float, int])
            self.assertTrue(type(ob_trade_event.amount) == float)
            self.assertTrue(type(ob_trade_event.price) == float)
            self.assertTrue(type(ob_trade_event.type) == TradeType)
            # datetime is in milliseconds
            self.assertTrue(math.ceil(math.log10(ob_trade_event.timestamp)) == 13)
            self.assertTrue(ob_trade_event.amount > 0)
            self.assertTrue(ob_trade_event.price > 0)

    def test_tracker_integrity(self):
        # Wait 5 seconds to process some diffs.
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        eth_usd: OrderBook = order_books["ETH-USD"]
        self.assertIsNot(eth_usd.last_diff_uid, 0)
        self.assertGreaterEqual(eth_usd.get_price_for_volume(True, 10).result_price,
                                eth_usd.get_price(True))
        self.assertLessEqual(eth_usd.get_price_for_volume(False, 10).result_price,
                             eth_usd.get_price(False))

    def test_api_get_last_traded_prices(self):
        prices = self.ev_loop.run_until_complete(
            CoinzoomAPIOrderBookDataSource.get_last_traded_prices(["BTC-USD", "LTC-BTC"]))
        for key, value in prices.items():
            print(f"{key} last_trade_price: {value}")
        self.assertGreater(prices["BTC-USD"], 1000)
        self.assertLess(prices["LTC-BTC"], 1)
