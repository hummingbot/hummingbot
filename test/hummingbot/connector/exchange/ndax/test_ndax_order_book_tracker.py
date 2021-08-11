#!/usr/bin/env python

import unittest
import asyncio


import hummingbot.connector.exchange.ndax.ndax_constants as CONSTANTS

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.connector.exchange.ndax.ndax_order_book import NdaxOrderBook
from hummingbot.connector.exchange.ndax.ndax_order_book_message import NdaxOrderBookEntry, NdaxOrderBookMessage
from hummingbot.connector.exchange.ndax.ndax_order_book_tracker import NdaxOrderBookTracker


class NdaxOrderBookTrackerUnitTest(unittest.TestCase):

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
        self.tracker: NdaxOrderBookTracker = NdaxOrderBookTracker([self.trading_pair])
        self.tracking_task = None

        # Simulate start()
        self.tracker._order_books[self.trading_pair] = NdaxOrderBook()
        self.tracker._tracking_message_queues[self.trading_pair] = asyncio.Queue()
        self.tracker._order_books_initialized.set()

    def tearDown(self) -> None:
        self.tracking_task and self.tracking_task.cancel()
        if len(self.tracker._tracking_tasks) > 0:
            for task in self.tracker._tracking_tasks.values():
                task.cancel()
        super().tearDown()

    def simulate_queue_order_book_messages(self, message: NdaxOrderBookMessage):
        message_queue = self.tracker._tracking_message_queues[self.trading_pair]
        message_queue.put_nowait(message)

    def simulate_saving_order_book_diff_messages(self, message: NdaxOrderBookMessage):
        message_queue = self.tracker._saved_message_queues[self.trading_pair]
        message_queue.put_nowait(message)

    def test_exchange_name(self):
        self.assertEqual(self.tracker.exchange_name, CONSTANTS.EXCHANGE_NAME)

    def test_track_single_book_apply_snapshot(self):
        snapshot_data = [
            NdaxOrderBookEntry(*[93617617, 1, 1626788175000, 0, 37800.0, 1, 37750.0, 1, 0.015, 0]),
            NdaxOrderBookEntry(*[93617617, 1, 1626788175000, 0, 37800.0, 1, 37751.0, 1, 0.015, 1])
        ]
        snapshot_msg = NdaxOrderBook.snapshot_message_from_exchange(
            msg={"data": snapshot_data},
            timestamp=1626788175000,
            metadata={"trading_pair": self.trading_pair, "instrument_id": self.instrument_id}
        )
        self.simulate_queue_order_book_messages(snapshot_msg)

        with self.assertRaises(asyncio.TimeoutError):
            # Allow 5 seconds for tracker to process some messages.
            self.tracking_task = self.ev_loop.create_task(asyncio.wait_for(
                self.tracker._track_single_book(self.trading_pair),
                2.0
            ))
            self.ev_loop.run_until_complete(self.tracking_task)

        self.assertEqual(0, self.tracker.order_books[self.trading_pair].snapshot_uid)

    def test_init_order_books(self):
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
