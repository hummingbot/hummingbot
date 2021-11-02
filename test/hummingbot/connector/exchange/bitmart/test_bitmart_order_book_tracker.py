#!/usr/bin/env python
import unittest
import asyncio
import json
import re
from aioresponses import aioresponses

import hummingbot.connector.exchange.bitmart.bitmart_constants as CONSTANTS
from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.exchange.bitmart.bitmart_order_book import BitmartOrderBook
from hummingbot.connector.exchange.bitmart.bitmart_order_book_message import BitmartOrderBookMessage
from hummingbot.connector.exchange.bitmart.bitmart_order_book_tracker import BitmartOrderBookTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BitmartOrderBookTrackerUnitTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker: BitmartOrderBookTracker = BitmartOrderBookTracker(throttler, [self.trading_pair])
        self.tracking_task = None

        # Simulate start()
        self.tracker._order_books[self.trading_pair] = BitmartOrderBook()
        self.tracker._tracking_message_queues[self.trading_pair] = asyncio.Queue()
        self.tracker._order_books_initialized.set()

    def tearDown(self) -> None:
        self.tracking_task and self.tracking_task.cancel()
        if len(self.tracker._tracking_tasks) > 0:
            for task in self.tracker._tracking_tasks.values():
                task.cancel()
        super().tearDown()

    def _example_snapshot(self):
        return {
            "data": {
                "timestamp": 1527777538000,
                "buys": [
                    {
                        "amount": "4800.00",
                        "total": "4800.00",
                        "price": "0.000767",
                        "count": "1"
                    },
                    {
                        "amount": "99996475.79",
                        "total": "100001275.79",
                        "price": "0.000201",
                        "count": "1"
                    },
                ],
                "sells": [
                    {
                        "amount": "100.00",
                        "total": "100.00",
                        "price": "0.007000",
                        "count": "1"
                    },
                    {
                        "amount": "6997.00",
                        "total": "7097.00",
                        "price": "1.000000",
                        "count": "1"
                    },
                ]
            }
        }

    def simulate_queue_order_book_messages(self, message: BitmartOrderBookMessage):
        message_queue = self.tracker._tracking_message_queues[self.trading_pair]
        message_queue.put_nowait(message)

    def test_track_single_book_apply_snapshot(self):
        snapshot_data = self._example_snapshot()
        snapshot_msg = BitmartOrderBook.snapshot_message_from_exchange(
            msg=snapshot_data,
            timestamp=snapshot_data["data"]["timestamp"],
            metadata={"trading_pair": self.trading_pair}
        )
        self.simulate_queue_order_book_messages(snapshot_msg)

        with self.assertRaises(asyncio.TimeoutError):
            # Allow 5 seconds for tracker to process some messages.
            self.tracking_task = self.ev_loop.create_task(asyncio.wait_for(
                self.tracker._track_single_book(self.trading_pair),
                2.0
            ))
            self.ev_loop.run_until_complete(self.tracking_task)

        self.assertEqual(1527777538000, self.tracker.order_books[self.trading_pair].snapshot_uid)

    @aioresponses()
    def test_init_order_books(self, mock_api):
        mock_response = self._example_snapshot()
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_api.get(regex_url, body=json.dumps(mock_response))
        self.tracker._order_books_initialized.clear()
        self.tracker._tracking_message_queues.clear()
        self.tracker._tracking_tasks.clear()
        self.tracker._order_books.clear()

        self.assertEqual(0, len(self.tracker.order_books))
        self.assertEqual(0, len(self.tracker._tracking_message_queues))
        self.assertEqual(0, len(self.tracker._tracking_tasks))
        self.assertFalse(self.tracker._order_books_initialized.is_set())

        init_order_books_task = self.ev_loop.create_task(
            self.tracker._init_order_books()
        )

        self.ev_loop.run_until_complete(init_order_books_task)

        self.assertIsInstance(self.tracker.order_books[self.trading_pair], OrderBook)
        self.assertTrue(self.tracker._order_books_initialized.is_set())

    @aioresponses()
    def test_can_get_price_after_order_book_init(self, mock_api):
        mock_response = self._example_snapshot()
        regex_url = re.compile(f"{CONSTANTS.REST_URL}/{CONSTANTS.GET_ORDER_BOOK_PATH_URL}")
        mock_api.get(regex_url, body=json.dumps(mock_response))

        init_order_books_task = self.ev_loop.create_task(
            self.tracker._init_order_books()
        )
        self.ev_loop.run_until_complete(init_order_books_task)

        ob = self.tracker.order_books[self.trading_pair]
        ask_price = ob.get_price(True)

        self.assertEqual(0.007, ask_price)
