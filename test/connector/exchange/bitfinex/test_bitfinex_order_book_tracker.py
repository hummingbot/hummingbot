#!/usr/bin/env python
import math
import time
from os.path import join, realpath
import sys
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderBookEvent, OrderBookTradeEvent, TradeType

import asyncio
import logging
from typing import Dict, Optional, List
import unittest

from hummingbot.connector.exchange.bitfinex.bitfinex_order_book_tracker import BitfinexOrderBookTracker
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.utils.async_utils import safe_ensure_future

sys.path.insert(0, realpath(join(__file__, "../../../../../")))


class BitfinexOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[BitfinexOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "BTC-USD",
    ]
    integrity_test_max_volume = 5  # Max volume in asks and bids for the book to be ready for tests
    daily_volume = 2500  # Approximate total daily volume in BTC for this exchange for sanity test
    book_enties = 5  # Number of asks and bids (each) for the book to be ready for tests

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: BitfinexOrderBookTracker = BitfinexOrderBookTracker(trading_pairs=cls.trading_pairs)
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        '''
        Wait until the order book under test fills as needed
        '''
        print("Waiting for order book to fill...")
        while True:
            book_present = cls.trading_pairs[0] in cls.order_book_tracker.order_books
            enough_asks = False
            enough_bids = False
            enough_ask_rows = False
            enough_bid_rows = False
            if book_present:
                ask_volume = sum(i.amount for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].ask_entries())
                ask_count = sum(1 for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].ask_entries())

                bid_volume = sum(i.amount for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].bid_entries())
                bid_count = sum(1 for i in cls.order_book_tracker.order_books[cls.trading_pairs[0]].bid_entries())

                enough_asks = ask_volume >= cls.integrity_test_max_volume
                enough_bids = bid_volume >= cls.integrity_test_max_volume

                enough_ask_rows = ask_count >= cls.book_enties
                enough_bid_rows = bid_count >= cls.book_enties

                print("Bid volume in book: %f (in %d bids), ask volume in book: %f (in %d asks)" % (bid_volume, bid_count, ask_volume, ask_count))

            if book_present and enough_asks and enough_bids and enough_ask_rows and enough_bid_rows:
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
        return self.ev_loop.run_until_complete(self.run_parallel_async(*tasks))

    def setUp(self):
        self.event_logger = EventLogger()
        for event_tag in self.events:
            for trading_pair, order_book in self.order_book_tracker.order_books.items():
                order_book.add_listener(event_tag, self.event_logger)

    def test_order_book_trade_event_emission(self):
        """2
        Tests if the order book tracker is able to retrieve order book trade message from exchange
        and emit order book trade events after correctly parsing the trade messages
        """
        self.run_parallel(self.event_logger.wait_for(OrderBookTradeEvent))
        for ob_trade_event in self.event_logger.event_log:
            self.assertTrue(type(ob_trade_event) == OrderBookTradeEvent)
            self.assertTrue(ob_trade_event.trading_pair in self.trading_pairs)
            self.assertTrue(type(ob_trade_event.timestamp) in [float, int])
            self.assertTrue(type(ob_trade_event.amount) == float)
            self.assertTrue(type(ob_trade_event.price) == float)
            self.assertTrue(type(ob_trade_event.type) == TradeType)
            # Bittrex datetime is in epoch milliseconds
            self.assertTrue(math.ceil(math.log10(ob_trade_event.timestamp)) == 10)
            self.assertTrue(ob_trade_event.amount > 0)
            self.assertTrue(ob_trade_event.price > 0)

    def test_tracker_integrity(self):
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        sut_book: OrderBook = order_books[self.trading_pairs[0]]

        # # 1 - test that best bid is less than best ask
        # self.assertGreater(sut_book.get_price(False), sut_book.get_price(True))

        # 2 - test that price to buy integrity_test_max_volume BTC is is greater than or equal to best ask
        self.assertGreaterEqual(sut_book.get_price_for_volume(True, self.integrity_test_max_volume).result_price,
                                sut_book.get_price(True))

        # 3 - test that price to sell integrity_test_max_volume BTC is is less than or equal to best bid
        self.assertLessEqual(sut_book.get_price_for_volume(False, self.integrity_test_max_volume).result_price,
                             sut_book.get_price(False))

        # 4 - test that all bids in order book are sorted by price in descending order
        previous_price = sys.float_info.max
        for bid_row in sut_book.bid_entries():
            self.assertTrue(previous_price >= bid_row.price)
            previous_price = bid_row.price

        # 5 - test that all asks in order book are sorted by price in ascending order
        previous_price = 0
        for ask_row in sut_book.ask_entries():
            self.assertTrue(previous_price <= ask_row.price)
            previous_price = ask_row.price

        # 6 - test that total volume in first   orders in book is less than 10 times
        # daily traded volumes for this exchange
        total_volume = 0
        count = 0
        for bid_row in sut_book.bid_entries():
            total_volume += bid_row.amount
            count += 1
            if count > self.book_enties:
                break
        count = 0
        for ask_row in sut_book.ask_entries():
            total_volume += ask_row.amount
            count += 1
            if count > self.book_enties:
                break
        self.assertLessEqual(total_volume, 10 * self.daily_volume)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
