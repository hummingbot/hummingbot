import asyncio
import time
import unittest
from collections import deque
from typing import Deque, Optional, Union

import hummingbot.connector.exchange.coinflex.coinflex_constants as CONSTANTS
from hummingbot.connector.exchange.coinflex.coinflex_order_book import CoinflexOrderBook
from hummingbot.connector.exchange.coinflex.coinflex_order_book_tracker import CoinflexOrderBookTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType


class CoinflexOrderBookTrackerUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ev_loop = asyncio.get_event_loop()

    def setUp(self) -> None:
        super().setUp()
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker: CoinflexOrderBookTracker = CoinflexOrderBookTracker(trading_pairs=[self.trading_pair],
                                                                          throttler=self.throttler)
        self.tracking_task: Optional[asyncio.Task] = None

        # Simulate start()
        self.tracker._order_books[self.trading_pair] = CoinflexOrderBook()
        self.tracker._tracking_message_queues[self.trading_pair] = asyncio.Queue()
        self.tracker._past_diffs_windows[self.trading_pair] = deque()
        self.tracker._order_books_initialized.set()

    def tearDown(self) -> None:
        self.tracking_task and self.tracking_task.cancel()
        super().tearDown()

    def _simulate_message_enqueue(self, message_queue: Union[asyncio.Queue, Deque], msg: OrderBookMessage):
        if isinstance(message_queue, asyncio.Queue):
            self.ev_loop.run_until_complete(message_queue.put(msg))
        elif isinstance(message_queue, Deque):
            message_queue.append(msg)
        else:
            raise NotImplementedError

    def test_exchange_name(self):
        self.assertEqual("coinflex", self.tracker.exchange_name)

        test_tracker = CoinflexOrderBookTracker(trading_pairs=[self.trading_pair],
                                                domain="coinflex_test",
                                                throttler=self.throttler)

        self.assertEqual("coinflex_test", test_tracker.exchange_name)

    def test_order_book_diff_router_trading_pair_not_found_append_to_saved_message_queue(self):
        expected_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": self.trading_pair,
            }
        )

        self._simulate_message_enqueue(self.tracker._order_book_diff_stream, expected_msg)

        self.tracker._tracking_message_queues.clear()

        task = self.ev_loop.create_task(
            self.tracker._order_book_diff_router()
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(0, len(self.tracker._tracking_message_queues))
        self.assertEqual(1, len(self.tracker._saved_message_queues[self.trading_pair]))
        task.cancel()

    def test_order_book_diff_router_snapshot_uid_above_diff_message_update_id(self):
        expected_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": self.trading_pair,
            }
        )

        self._simulate_message_enqueue(self.tracker._order_book_diff_stream, expected_msg)

        task = self.ev_loop.create_task(
            self.tracker._order_book_diff_router()
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(1, self.tracker._tracking_message_queues[self.trading_pair].qsize())
        task.cancel()

    def test_order_book_diff_router_snapshot_uid_below_diff_message_update_id(self):
        # Updates the snapshot_uid
        self.tracker.order_books[self.trading_pair].apply_snapshot([], [], 2)
        expected_msg: OrderBookMessage = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": self.trading_pair,
            }
        )

        self._simulate_message_enqueue(self.tracker._order_book_diff_stream, expected_msg)

        task = self.ev_loop.create_task(
            self.tracker._order_book_diff_router()
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(0, self.tracker._tracking_message_queues[self.trading_pair].qsize())
        task.cancel()

    def test_track_single_book_snapshot_message_no_past_diffs(self):
        snapshot_msg: OrderBookMessage = CoinflexOrderBook.snapshot_message_from_exchange(
            msg={
                "marketCode": self.trading_pair,
                "timestamp": 1,
                "bids": [
                    ["4.00000000", "431.00000000"]
                ],
                "asks": [
                    ["4.00000200", "12.00000000"]
                ]
            },
            timestamp=time.time(),
            metadata={"trading_pair": self.trading_pair}
        )
        self._simulate_message_enqueue(self.tracker._tracking_message_queues[self.trading_pair], snapshot_msg)

        self.tracking_task = self.ev_loop.create_task(
            self.tracker._track_single_book(self.trading_pair)
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))
        self.assertEqual(1, self.tracker.order_books[self.trading_pair].snapshot_uid)

    def test_track_single_book_snapshot_message_with_past_diffs(self):
        snapshot_msg: OrderBookMessage = CoinflexOrderBook.snapshot_message_from_exchange(
            msg={
                "marketCode": self.trading_pair,
                "timestamp": 1,
                "bids": [
                    ["4.00000000", "431.00000000"]
                ],
                "asks": [
                    ["4.00000200", "12.00000000"]
                ]
            },
            timestamp=time.time(),
            metadata={"trading_pair": self.trading_pair}
        )
        past_diff_msg: OrderBookMessage = CoinflexOrderBook.diff_message_from_exchange(
            msg={
                "table": "depth",
                "data": [{
                    "timestamp": 2,
                    "instrumentId": "BNBBTC",
                    "seqNum": 123456789,
                    "bids": [
                        [
                            "0.0024",
                            "10"
                        ]
                    ],
                    "asks": [
                        [
                            "0.0026",
                            "100"
                        ]
                    ]
                }]
            },
            metadata={"trading_pair": self.trading_pair}
        )

        self.tracking_task = self.ev_loop.create_task(
            self.tracker._track_single_book(self.trading_pair)
        )

        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self._simulate_message_enqueue(self.tracker._past_diffs_windows[self.trading_pair], past_diff_msg)
        self._simulate_message_enqueue(self.tracker._tracking_message_queues[self.trading_pair], snapshot_msg)

        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(1, self.tracker.order_books[self.trading_pair].snapshot_uid)
        self.assertEqual(2, self.tracker.order_books[self.trading_pair].last_diff_uid)

    def test_track_single_book_diff_message(self):
        diff_msg: OrderBookMessage = CoinflexOrderBook.diff_message_from_exchange(
            msg={
                "table": "depth",
                "data": [{
                    "timestamp": 2,
                    "instrumentId": "BNBBTC",
                    "seqNum": 123456789,
                    "bids": [
                        [
                            "0.0024",
                            "10"
                        ]
                    ],
                    "asks": [
                        [
                            "0.0026",
                            "100"
                        ]
                    ]
                }]
            },
            metadata={"trading_pair": self.trading_pair}
        )

        self._simulate_message_enqueue(self.tracker._tracking_message_queues[self.trading_pair], diff_msg)

        self.tracking_task = self.ev_loop.create_task(
            self.tracker._track_single_book(self.trading_pair)
        )
        self.ev_loop.run_until_complete(asyncio.sleep(0.5))

        self.assertEqual(0, self.tracker.order_books[self.trading_pair].snapshot_uid)
        self.assertEqual(2, self.tracker.order_books[self.trading_pair].last_diff_uid)
