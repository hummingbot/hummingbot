#!/usr/bin/env python
import unittest
import asyncio
from collections import Awaitable
from decimal import Decimal
from typing import Any
from unittest.mock import patch, AsyncMock

import hummingbot.connector.exchange.mexc.mexc_constants as CONSTANTS

from hummingbot.core.data_type.order_book import OrderBook

from hummingbot.connector.exchange.mexc.mexc_order_book import MexcOrderBook
from hummingbot.connector.exchange.mexc.mexc_order_book_message import MexcOrderBookMessage
from hummingbot.connector.exchange.mexc.mexc_order_book_tracker import MexcOrderBookTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class MexcOrderBookTrackerUnitTest(unittest.TestCase):

    @property
    def content(self):
        return {"asks": [{"price": "37751.0", "quantity": "0.015"}],
                "bids": [{"price": "37750.0", "quantity": "0.015"}]}

    @property
    def mock_data(self):
        _data = {"code": 200, "data": {
            "asks": [{"price": "56454.0", "quantity": "0.799072"}, {"price": "56455.28", "quantity": "0.008663"}],
            "bids": [{"price": "56451.0", "quantity": "0.008663"}, {"price": "56449.99", "quantity": "0.173078"}],
            "version": "547878563"}}
        return _data

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.instrument_id = 1

        cls.ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker: MexcOrderBookTracker = MexcOrderBookTracker(throttler=throttler,
                                                                  trading_pairs=[self.trading_pair])
        self.tracking_task = None

        # Simulate start()
        self.tracker._order_books[self.trading_pair] = MexcOrderBook()
        self.tracker._tracking_message_queues[self.trading_pair] = asyncio.Queue()
        self.tracker._order_books_initialized.set()

    def tearDown(self) -> None:
        self.tracking_task and self.tracking_task.cancel()
        if len(self.tracker._tracking_tasks) > 0:
            for task in self.tracker._tracking_tasks.values():
                task.cancel()
        super().tearDown()

    @staticmethod
    def set_mock_response(mock_api, status: int, json_data: Any):
        mock_api.return_value.__aenter__.return_value.status = status
        mock_api.return_value.__aenter__.return_value.json = AsyncMock(return_value=json_data)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def simulate_queue_order_book_messages(self, message: MexcOrderBookMessage):
        message_queue = self.tracker._tracking_message_queues[self.trading_pair]
        message_queue.put_nowait(message)

    def test_exchange_name(self):
        self.assertEqual(self.tracker.exchange_name, CONSTANTS.EXCHANGE_NAME)

    def test_track_single_book_apply_snapshot(self):
        snapshot_msg = MexcOrderBook.snapshot_message_from_exchange(
            msg=self.content,
            timestamp=1626788175000,
            trading_pair=self.trading_pair
        )
        self.simulate_queue_order_book_messages(snapshot_msg)

        with self.assertRaises(asyncio.TimeoutError):
            # Allow 5 seconds for tracker to process some messages.
            self.tracking_task = self.ev_loop.create_task(asyncio.wait_for(
                self.tracker._track_single_book(self.trading_pair),
                2.0
            ))
            self.async_run_with_timeout(self.tracking_task)

        self.assertEqual(1626788175000000, self.tracker.order_books[self.trading_pair].snapshot_uid)

    @patch("aiohttp.ClientSession.get")
    def test_init_order_books(self, mock_api):
        self.set_mock_response(mock_api, 200, self.mock_data)

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

        self.async_run_with_timeout(init_order_books_task)

        self.assertIsInstance(self.tracker.order_books[self.trading_pair], OrderBook)
        self.assertTrue(self.tracker._order_books_initialized.is_set())

    @patch("aiohttp.ClientSession.get")
    def test_can_get_price_after_order_book_init(self, mock_api):
        self.set_mock_response(mock_api, 200, self.mock_data)

        init_order_books_task = self.ev_loop.create_task(
            self.tracker._init_order_books()
        )
        self.async_run_with_timeout(init_order_books_task)

        ob = self.tracker.order_books[self.trading_pair]
        ask_price = ob.get_price(True)
        self.assertEqual(Decimal("56454.0"), ask_price)
