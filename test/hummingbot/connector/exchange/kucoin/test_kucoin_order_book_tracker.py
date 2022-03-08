import asyncio
from collections import deque
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

import hummingbot.connector.exchange.kucoin.kucoin_constants as CONSTANTS
from hummingbot.connector.exchange.kucoin.kucoin_order_book import KucoinOrderBook
from hummingbot.connector.exchange.kucoin.kucoin_order_book_message import KucoinOrderBookMessage
from hummingbot.connector.exchange.kucoin.kucoin_order_book_tracker import KucoinOrderBookTracker
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.data_type.order_book_message import OrderBookMessageType
from hummingbot.core.data_type.order_book_row import OrderBookRow


class KucoinOrderBookTrackerTests(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        self.tracker: KucoinOrderBookTracker = KucoinOrderBookTracker(trading_pairs=[self.trading_pair],
                                                                      throttler=self.throttler)
        self.async_task = None

        # Simulate start()
        self.tracker._order_books[self.trading_pair] = KucoinOrderBook()
        self.tracker._tracking_message_queues[self.trading_pair] = asyncio.Queue()
        self.tracker._past_diffs_windows[self.trading_pair] = deque()
        self.tracker._order_books_initialized.set()

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        super().tearDown()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_diff_message_routed_to_saved_messages_queue_when_order_book_not_present(self):
        unknown_trading_pair_msg = KucoinOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": "UNK-UNK",
            }
        )

        known_trading_pair_msg = KucoinOrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "update_id": 1,
                "trading_pair": self.trading_pair,
            }
        )

        self.tracker._order_book_diff_stream.put_nowait(unknown_trading_pair_msg)
        self.tracker._order_book_diff_stream.put_nowait(known_trading_pair_msg)

        self.tracker._tracking_message_queues.clear()
        self.tracker._tracking_message_queues[self.trading_pair] = asyncio.Queue()

        self.async_task = asyncio.get_event_loop().create_task(
            self.tracker._order_book_diff_router()
        )
        routed_message = self.async_run_with_timeout(self.tracker._tracking_message_queues[self.trading_pair].get())

        self.assertEqual(1, len(self.tracker._saved_message_queues["UNK-UNK"]))
        self.assertEqual(unknown_trading_pair_msg, self.tracker._saved_message_queues["UNK-UNK"][0])
        self.assertEqual(1, len(self.tracker._tracking_message_queues))
        self.assertEqual(known_trading_pair_msg, routed_message)

    def test_track_single_book_snapshot_message_no_past_diffs(self):
        processed_messages = asyncio.Queue()
        mock_order_book = MagicMock()
        mock_order_book.restore_from_snapshot_and_diffs.side_effect = (lambda message, past_diffs:
                                                                       processed_messages.put_nowait(message))
        self.tracker._order_books[self.trading_pair] = mock_order_book

        snapshot_msg = KucoinOrderBook.snapshot_message_from_exchange(
            msg={
                "symbol": self.trading_pair,
                "data": {
                    "sequence": 1,
                    "bids": [
                        ["4.00000000", "431.00000000"]
                    ],
                    "asks": [
                        ["4.00000200", "12.00000000"]
                    ]}
            },
            timestamp=1640001112.223
        )
        self.tracker._tracking_message_queues[self.trading_pair].put_nowait(snapshot_msg)

        self.async_task = asyncio.get_event_loop().create_task(
            self.tracker._track_single_book(self.trading_pair)
        )

        processed_snapshot = self.async_run_with_timeout(processed_messages.get())
        self.assertEqual(snapshot_msg, processed_snapshot)

    def test_track_single_book_snapshot_message_with_past_diffs(self):
        processed_past_diffs = asyncio.Queue()
        mock_order_book = MagicMock()
        mock_order_book.restore_from_snapshot_and_diffs.side_effect = (lambda message, past_diffs:
                                                                       processed_past_diffs.put_nowait(past_diffs))
        self.tracker._order_books[self.trading_pair] = mock_order_book

        snapshot_msg = KucoinOrderBook.snapshot_message_from_exchange(
            msg={
                "symbol": self.trading_pair,
                "data": {
                    "sequence": 1,
                    "bids": [
                        ["4.00000000", "431.00000000"]
                    ],
                    "asks": [
                        ["4.00000200", "12.00000000"]
                    ]}
            },
            timestamp=1640001112.223
        )
        past_diff_msg = KucoinOrderBook.diff_message_from_exchange(
            msg={
                "data": {
                    "symbol": self.trading_pair,
                    "sequenceStart": 1,
                    "sequenceEnd": 2,
                    "changes": {
                        "bids": [["0.0024", "10", "1"]],
                        "asks": [["0.0026", "100", "2"]]}},
            },
            metadata={"symbol": self.trading_pair},
            timestamp=1640001110.223
        )

        self.async_task = asyncio.get_event_loop().create_task(
            self.tracker._track_single_book(self.trading_pair)
        )

        self.tracker._past_diffs_windows[self.trading_pair].append(past_diff_msg)
        self.tracker._tracking_message_queues[self.trading_pair].put_nowait(snapshot_msg)

        processed_diffs = self.async_run_with_timeout(processed_past_diffs.get())
        self.assertEqual(1, len(processed_diffs))
        self.assertEqual(past_diff_msg, processed_diffs[0])

    def test_track_single_book_diff_message(self):
        processed_past_diffs = asyncio.Queue()
        mock_order_book = MagicMock()
        mock_order_book.apply_diffs.side_effect = (lambda bids, asks, update_id:
                                                   processed_past_diffs.put_nowait([bids, asks, update_id]))
        self.tracker._order_books[self.trading_pair] = mock_order_book

        diff_msg = KucoinOrderBook.diff_message_from_exchange(
            msg={
                "data": {
                    "symbol": self.trading_pair,
                    "sequenceStart": 1,
                    "sequenceEnd": 2,
                    "changes": {
                        "bids": [["0.0024", "10", "1"]],
                        "asks": [["0.0026", "100", "2"]]}},
            },
            metadata={"symbol": self.trading_pair},
            timestamp=1640001110.223
        )

        self.async_task = asyncio.get_event_loop().create_task(
            self.tracker._track_single_book(self.trading_pair)
        )

        self.tracker._tracking_message_queues[self.trading_pair].put_nowait(diff_msg)

        processed_diff = self.async_run_with_timeout(processed_past_diffs.get())
        bids, asks, update_id = processed_diff
        self.assertEqual(1, len(bids))
        bid: OrderBookRow = bids[0]
        self.assertEqual(0.0024, bid.price)
        self.assertEqual(10, bid.amount)
        self.assertEqual(1640001110223, bid.update_id)
        self.assertEqual(1, len(asks))
        ask: OrderBookRow = asks[0]
        self.assertEqual(0.0026, ask.price)
        self.assertEqual(100, ask.amount)
        self.assertEqual(1640001110223, ask.update_id)

    def test_track_single_book_raises_cancelled_error(self):
        mock_order_book = MagicMock()
        mock_order_book.apply_diffs.side_effect = asyncio.CancelledError("Test cancellation")
        self.tracker._order_books[self.trading_pair] = mock_order_book

        diff_msg = KucoinOrderBook.diff_message_from_exchange(
            msg={
                "data": {
                    "symbol": self.trading_pair,
                    "sequenceStart": 1,
                    "sequenceEnd": 2,
                    "changes": {
                        "bids": [["0.0024", "10", "1"]],
                        "asks": [["0.0026", "100", "2"]]}},
            },
            metadata={"symbol": self.trading_pair},
            timestamp=1640001110.223
        )

        self.tracker._tracking_message_queues[self.trading_pair].put_nowait(diff_msg)

        try:
            self.async_run_with_timeout(self.tracker._track_single_book(self.trading_pair))
            self.fail("The process should have raised CancelledError exception")
        except asyncio.CancelledError:
            pass
        except Exception:
            self.fail("The process should only raise CancelledError exception")
