#!/usr/bin/env python
import math
from os.path import (
    join,
    realpath
)
import sys; sys.path.insert(0, realpath(join(__file__, "../../../../../")))
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import (
    OrderBookTradeEvent,
    TradeType,
    OrderBookEvent
)
import asyncio
import logging
import unittest
from datetime import datetime
from decimal import Decimal
from typing import (
    Dict,
    Optional,
    List,
)
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book_tracker import CoinbaseProOrderBookTracker
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_api_order_book_data_source import CoinbaseProAPIOrderBookDataSource
from hummingbot.connector.exchange.coinbase_pro.coinbase_pro_order_book import CoinbaseProOrderBook
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_tracker import (
    OrderBookTrackerDataSource
)
from hummingbot.core.utils.async_utils import (
    safe_ensure_future,
    safe_gather,
)


class CoinbaseProOrderBookTrackerUnitTest(unittest.TestCase):
    order_book_tracker: Optional[CoinbaseProOrderBookTracker] = None
    events: List[OrderBookEvent] = [
        OrderBookEvent.TradeEvent
    ]
    trading_pairs: List[str] = [
        "BTC-USD"
    ]

    @classmethod
    def setUpClass(cls):
        cls.ev_loop: asyncio.BaseEventLoop = asyncio.get_event_loop()
        cls.order_book_tracker: CoinbaseProOrderBookTracker = CoinbaseProOrderBookTracker(
            trading_pairs=cls.trading_pairs)
        cls.order_book_tracker_task: asyncio.Task = safe_ensure_future(cls.order_book_tracker.start())
        cls.ev_loop.run_until_complete(cls.wait_til_tracker_ready())

    @classmethod
    async def wait_til_tracker_ready(cls):
        await cls.order_book_tracker._order_books_initialized.wait()
        # while True:
        #     if len(cls.order_book_tracker.order_books) > 0:
        #         print("Initialized real-time order books.")
        #         return
        #     await asyncio.sleep(1)

    async def run_parallel_async(self, *tasks, timeout=None):
        future: asyncio.Future = safe_ensure_future(safe_gather(*tasks))
        timer = 0
        while not future.done():
            if timeout and timer > timeout:
                raise Exception("Time out running parallel async task in tests.")
            timer += 1
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
        """
        Test if order book tracker is able to retrieve order book trade message from exchange and
        emit order book trade events after correctly parsing the trade messages
        """
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
        self.ev_loop.run_until_complete(asyncio.sleep(5.0))
        order_books: Dict[str, OrderBook] = self.order_book_tracker.order_books
        test_order_book: OrderBook = order_books["BTC-USD"]
        # print("test_order_book")
        # print(test_order_book.snapshot)
        self.assertGreaterEqual(test_order_book.get_price_for_volume(True, 10).result_price,
                                test_order_book.get_price(True))
        self.assertLessEqual(test_order_book.get_price_for_volume(False, 10).result_price,
                             test_order_book.get_price(False))

        test_active_order_tracker = self.order_book_tracker._active_order_trackers["BTC-USD"]
        self.assertTrue(len(test_active_order_tracker.active_asks) > 0)
        self.assertTrue(len(test_active_order_tracker.active_bids) > 0)
        for order_book in self.order_book_tracker.order_books.values():
            # print(order_book.last_trade_price)
            self.assertFalse(math.isnan(order_book.last_trade_price))

    def test_order_book_data_source(self):
        self.assertTrue(isinstance(self.order_book_tracker.data_source, OrderBookTrackerDataSource))

    def test_diff_msg_get_added_to_order_book(self):
        test_active_order_tracker = self.order_book_tracker._active_order_trackers["BTC-USD"]

        price = "200"
        order_id = "test_order_id"
        product_id = "BTC-USD"
        remaining_size = "1.00"

        # Test open message diff
        raw_open_message = {
            "type": "open",
            "time": datetime.now().isoformat(),
            "product_id": product_id,
            "sequence": 20000000000,
            "order_id": order_id,
            "price": price,
            "remaining_size": remaining_size,
            "side": "buy"
        }
        open_message = CoinbaseProOrderBook.diff_message_from_exchange(raw_open_message)
        self.order_book_tracker._order_book_diff_stream.put_nowait(open_message)
        self.run_parallel(asyncio.sleep(5))

        test_order_book_row = test_active_order_tracker.active_bids[Decimal(price)]
        self.assertEqual(test_order_book_row[order_id]["remaining_size"], remaining_size)

        # Test change message diff
        new_size = "2.00"
        raw_change_message = {
            "type": "change",
            "time": datetime.now().isoformat(),
            "product_id": product_id,
            "sequence": 20000000001,
            "order_id": order_id,
            "price": price,
            "new_size": new_size,
            "old_size": remaining_size,
            "side": "buy",
        }
        change_message = CoinbaseProOrderBook.diff_message_from_exchange(raw_change_message)
        self.order_book_tracker._order_book_diff_stream.put_nowait(change_message)
        self.run_parallel(asyncio.sleep(5))

        test_order_book_row = test_active_order_tracker.active_bids[Decimal(price)]
        self.assertEqual(test_order_book_row[order_id]["remaining_size"], new_size)

        # Test match message diff
        match_size = "0.50"
        raw_match_message = {
            "type": "match",
            "trade_id": 10,
            "sequence": 20000000002,
            "maker_order_id": order_id,
            "taker_order_id": "test_order_id_2",
            "time": datetime.now().isoformat(),
            "product_id": "BTC-USD",
            "size": match_size,
            "price": price,
            "side": "buy"
        }
        match_message = CoinbaseProOrderBook.diff_message_from_exchange(raw_match_message)
        self.order_book_tracker._order_book_diff_stream.put_nowait(match_message)
        self.run_parallel(asyncio.sleep(5))

        test_order_book_row = test_active_order_tracker.active_bids[Decimal(price)]
        self.assertEqual(Decimal(test_order_book_row[order_id]["remaining_size"]),
                         Decimal(new_size) - Decimal(match_size))

        # Test done message diff
        raw_done_message = {
            "type": "done",
            "time": datetime.now().isoformat(),
            "product_id": "BTC-USD",
            "sequence": 20000000003,
            "price": price,
            "order_id": order_id,
            "reason": "filled",
            "remaining_size": 0,
            "side": "buy",
        }
        done_message = CoinbaseProOrderBook.diff_message_from_exchange(raw_done_message)
        self.order_book_tracker._order_book_diff_stream.put_nowait(done_message)
        self.run_parallel(asyncio.sleep(5))

        test_order_book_row = test_active_order_tracker.active_bids[Decimal(price)]
        self.assertTrue(order_id not in test_order_book_row)

    def test_api_get_last_traded_prices(self):
        prices = self.ev_loop.run_until_complete(
            CoinbaseProAPIOrderBookDataSource.get_last_traded_prices(["BTC-USD", "LTC-USD"]))
        for key, value in prices.items():
            print(f"{key} last_trade_price: {value}")
        self.assertGreater(prices["BTC-USD"], 1000)
        self.assertLess(prices["LTC-USD"], 1000)


def main():
    logging.basicConfig(level=logging.INFO)
    unittest.main()


if __name__ == "__main__":
    main()
