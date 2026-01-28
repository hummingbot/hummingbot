#!/usr/bin/env python
"""
Tests for OrderBookTracker and its metrics classes.

This module tests:
- LatencyStats: Latency tracking with sampling and rolling windows
- OrderBookPairMetrics: Per-pair metrics tracking
- OrderBookTrackerMetrics: Aggregate metrics tracking
- OrderBookTracker: Integration tests for metrics in the tracker
"""
import asyncio
import time
import unittest
from collections import deque
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

import numpy as np

from hummingbot.core.data_type.order_book import OrderBook
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker import (
    LatencyStats,
    OrderBookPairMetrics,
    OrderBookTracker,
    OrderBookTrackerMetrics,
)
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource


def create_order_book_with_snapshot_uid(snapshot_uid: int) -> OrderBook:
    """Create an OrderBook with a specific snapshot_uid."""
    ob = OrderBook()
    # Use numpy snapshot to set the snapshot_uid (update_id is the third column)
    bids = np.array([[100.0, 1.0, float(snapshot_uid)]], dtype=np.float64)
    asks = np.array([[101.0, 1.0, float(snapshot_uid)]], dtype=np.float64)
    ob.apply_numpy_snapshot(bids, asks)
    return ob


class LatencyStatsTests(unittest.TestCase):
    """Tests for the LatencyStats dataclass."""

    def test_initial_values(self):
        """Test that LatencyStats initializes with correct default values."""
        stats = LatencyStats()

        self.assertEqual(0, stats.count)
        self.assertEqual(0.0, stats.total_ms)
        self.assertEqual(float('inf'), stats.min_ms)
        self.assertEqual(0.0, stats.max_ms)
        self.assertEqual(0.0, stats.avg_ms)
        self.assertEqual(0.0, stats.recent_avg_ms)
        self.assertEqual(0, stats.recent_samples_count)

    def test_record_single_sample(self):
        """Test recording a single latency sample."""
        stats = LatencyStats()
        stats.record(5.0)

        self.assertEqual(1, stats.count)
        self.assertEqual(5.0, stats.min_ms)
        self.assertEqual(5.0, stats.max_ms)

    def test_record_multiple_samples_updates_min_max(self):
        """Test that min/max are updated correctly across multiple samples."""
        stats = LatencyStats()

        stats.record(10.0)
        stats.record(5.0)
        stats.record(15.0)
        stats.record(8.0)

        self.assertEqual(4, stats.count)
        self.assertEqual(5.0, stats.min_ms)
        self.assertEqual(15.0, stats.max_ms)

    def test_sampling_behavior(self):
        """Test that full stats are only recorded every SAMPLE_RATE messages."""
        stats = LatencyStats()
        stats.SAMPLE_RATE = 10  # Record every 10th message

        # Record 25 samples
        for i in range(25):
            stats.record(1.0)

        self.assertEqual(25, stats.count)
        # Only 2 full samples should be in recent_samples (at 10 and 20)
        self.assertEqual(2, stats.recent_samples_count)

    def test_avg_ms_calculation(self):
        """Test average latency calculation with sampling."""
        stats = LatencyStats()
        stats.SAMPLE_RATE = 1  # Record every message for this test

        stats.record(10.0)
        stats.record(20.0)
        stats.record(30.0)

        # With SAMPLE_RATE=1, total_ms = 10 + 20 + 30 = 60
        self.assertEqual(20.0, stats.avg_ms)

    def test_recent_avg_ms_calculation(self):
        """Test recent average with rolling window."""
        stats = LatencyStats()
        stats.SAMPLE_RATE = 1  # Record every message

        for i in range(5):
            stats.record(float(i + 1))  # 1, 2, 3, 4, 5

        # Recent samples: [1, 2, 3, 4, 5], avg = 15/5 = 3.0
        self.assertEqual(3.0, stats.recent_avg_ms)

    def test_rolling_window_size_limit(self):
        """Test that rolling window respects size limit."""
        stats = LatencyStats()
        stats.SAMPLE_RATE = 1
        stats._recent_samples = deque(maxlen=5)  # Small window for testing

        # Record more samples than window size
        for i in range(10):
            stats.record(float(i))

        # Should only have last 5 samples
        self.assertEqual(5, stats.recent_samples_count)

    def test_to_dict_serialization(self):
        """Test that to_dict returns correct structure."""
        stats = LatencyStats()
        stats.record(5.0)
        stats.record(10.0)

        result = stats.to_dict()

        self.assertIn("count", result)
        self.assertIn("total_ms", result)
        self.assertIn("min_ms", result)
        self.assertIn("max_ms", result)
        self.assertIn("avg_ms", result)
        self.assertIn("recent_avg_ms", result)
        self.assertIn("recent_samples_count", result)

        self.assertEqual(2, result["count"])
        self.assertEqual(5.0, result["min_ms"])
        self.assertEqual(10.0, result["max_ms"])

    def test_to_dict_handles_infinity(self):
        """Test that to_dict converts infinity min_ms to 0."""
        stats = LatencyStats()  # No samples recorded

        result = stats.to_dict()

        self.assertEqual(0.0, result["min_ms"])


class OrderBookPairMetricsTests(unittest.TestCase):
    """Tests for the OrderBookPairMetrics dataclass."""

    def test_initialization(self):
        """Test that pair metrics initializes correctly."""
        metrics = OrderBookPairMetrics(trading_pair="BTC-USDT")

        self.assertEqual("BTC-USDT", metrics.trading_pair)
        self.assertEqual(0, metrics.diffs_processed)
        self.assertEqual(0, metrics.diffs_rejected)
        self.assertEqual(0, metrics.snapshots_processed)
        self.assertEqual(0, metrics.trades_processed)
        self.assertEqual(0, metrics.trades_rejected)

    def test_messages_per_minute_calculation(self):
        """Test messages per minute rate calculation."""
        metrics = OrderBookPairMetrics(
            trading_pair="BTC-USDT",
            tracking_start_time=100.0,
            diffs_processed=120,
            snapshots_processed=2,
            trades_processed=60,
        )

        # Current time is 160 (60 seconds elapsed = 1 minute)
        rates = metrics.messages_per_minute(160.0)

        self.assertEqual(120.0, rates["diffs"])
        self.assertEqual(2.0, rates["snapshots"])
        self.assertEqual(60.0, rates["trades"])
        self.assertEqual(182.0, rates["total"])

    def test_messages_per_minute_zero_elapsed(self):
        """Test that messages_per_minute handles zero elapsed time."""
        metrics = OrderBookPairMetrics(
            trading_pair="BTC-USDT",
            tracking_start_time=0,
        )

        rates = metrics.messages_per_minute(0)

        self.assertEqual(0.0, rates["diffs"])
        self.assertEqual(0.0, rates["total"])

    def test_to_dict_serialization(self):
        """Test that to_dict returns all required fields."""
        metrics = OrderBookPairMetrics(
            trading_pair="ETH-USDT",
            diffs_processed=100,
            trades_processed=50,
            tracking_start_time=100.0,
        )

        result = metrics.to_dict(160.0)

        self.assertEqual("ETH-USDT", result["trading_pair"])
        self.assertEqual(100, result["diffs_processed"])
        self.assertEqual(50, result["trades_processed"])
        self.assertIn("messages_per_minute", result)
        self.assertIn("diff_latency", result)
        self.assertIn("snapshot_latency", result)
        self.assertIn("trade_latency", result)


class OrderBookTrackerMetricsTests(unittest.TestCase):
    """Tests for the OrderBookTrackerMetrics dataclass."""

    def test_initialization(self):
        """Test that tracker metrics initializes correctly."""
        metrics = OrderBookTrackerMetrics()

        self.assertEqual(0, metrics.total_diffs_processed)
        self.assertEqual(0, metrics.total_diffs_rejected)
        self.assertEqual(0, metrics.total_diffs_queued)
        self.assertEqual(0, metrics.total_snapshots_processed)
        self.assertEqual(0, metrics.total_trades_processed)
        self.assertEqual({}, metrics.per_pair_metrics)

    def test_get_or_create_pair_metrics_creates_new(self):
        """Test that get_or_create_pair_metrics creates new metrics."""
        metrics = OrderBookTrackerMetrics()

        pair_metrics = metrics.get_or_create_pair_metrics("BTC-USDT")

        self.assertIn("BTC-USDT", metrics.per_pair_metrics)
        self.assertEqual("BTC-USDT", pair_metrics.trading_pair)
        self.assertGreater(pair_metrics.tracking_start_time, 0)

    def test_get_or_create_pair_metrics_returns_existing(self):
        """Test that get_or_create_pair_metrics returns existing metrics."""
        metrics = OrderBookTrackerMetrics()

        pair_metrics1 = metrics.get_or_create_pair_metrics("BTC-USDT")
        pair_metrics1.diffs_processed = 100

        pair_metrics2 = metrics.get_or_create_pair_metrics("BTC-USDT")

        self.assertIs(pair_metrics1, pair_metrics2)
        self.assertEqual(100, pair_metrics2.diffs_processed)

    def test_remove_pair_metrics(self):
        """Test that remove_pair_metrics removes metrics correctly."""
        metrics = OrderBookTrackerMetrics()

        metrics.get_or_create_pair_metrics("BTC-USDT")
        metrics.get_or_create_pair_metrics("ETH-USDT")

        self.assertEqual(2, len(metrics.per_pair_metrics))

        metrics.remove_pair_metrics("BTC-USDT")

        self.assertEqual(1, len(metrics.per_pair_metrics))
        self.assertNotIn("BTC-USDT", metrics.per_pair_metrics)
        self.assertIn("ETH-USDT", metrics.per_pair_metrics)

    def test_remove_pair_metrics_nonexistent(self):
        """Test that removing nonexistent pair doesn't raise error."""
        metrics = OrderBookTrackerMetrics()

        # Should not raise
        metrics.remove_pair_metrics("NONEXISTENT")

    def test_messages_per_minute_global(self):
        """Test global messages per minute calculation."""
        metrics = OrderBookTrackerMetrics()
        metrics.tracker_start_time = 100.0
        metrics.total_diffs_processed = 600
        metrics.total_snapshots_processed = 6
        metrics.total_trades_processed = 300

        # 60 seconds elapsed = 1 minute
        rates = metrics.messages_per_minute(160.0)

        self.assertEqual(600.0, rates["diffs"])
        self.assertEqual(6.0, rates["snapshots"])
        self.assertEqual(300.0, rates["trades"])
        self.assertEqual(906.0, rates["total"])

    def test_to_dict_serialization(self):
        """Test that to_dict returns comprehensive data."""
        metrics = OrderBookTrackerMetrics()
        metrics.tracker_start_time = time.perf_counter() - 60  # 60 seconds ago
        metrics.total_diffs_processed = 100
        metrics.get_or_create_pair_metrics("BTC-USDT")

        result = metrics.to_dict()

        self.assertIn("total_diffs_processed", result)
        self.assertIn("total_snapshots_processed", result)
        self.assertIn("total_trades_processed", result)
        self.assertIn("uptime_seconds", result)
        self.assertIn("messages_per_minute", result)
        self.assertIn("diff_latency", result)
        self.assertIn("per_pair_metrics", result)
        self.assertIn("BTC-USDT", result["per_pair_metrics"])


class OrderBookTrackerMetricsIntegrationTests(IsolatedAsyncioWrapperTestCase):
    """Integration tests for OrderBookTracker with metrics."""

    def setUp(self):
        super().setUp()
        self.data_source = MagicMock(spec=OrderBookTrackerDataSource)
        self.trading_pairs = ["BTC-USDT", "ETH-USDT"]

    def _create_tracker(self):
        """Create a tracker instance for testing."""
        return OrderBookTracker(
            data_source=self.data_source,
            trading_pairs=self.trading_pairs,
        )

    def test_metrics_property_exists(self):
        """Test that tracker has metrics property."""
        tracker = self._create_tracker()

        self.assertIsInstance(tracker.metrics, OrderBookTrackerMetrics)

    def test_start_sets_tracker_start_time(self):
        """Test that start() sets the tracker start time."""
        tracker = self._create_tracker()

        self.assertEqual(0.0, tracker.metrics.tracker_start_time)

        # Mock the data source methods to prevent actual async operations
        self.data_source.listen_for_order_book_diffs = AsyncMock()
        self.data_source.listen_for_trades = AsyncMock()
        self.data_source.listen_for_order_book_snapshots = AsyncMock()
        self.data_source.listen_for_subscriptions = AsyncMock()
        self.data_source.get_new_order_book = AsyncMock(return_value=OrderBook())

        tracker.start()

        self.assertGreater(tracker.metrics.tracker_start_time, 0)

        tracker.stop()

    async def test_diff_router_updates_metrics(self):
        """Test that diff router updates metrics correctly."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()

        # Set up order book with snapshot_uid=100 and tracking queue
        order_book = create_order_book_with_snapshot_uid(100)
        tracker._order_books["BTC-USDT"] = order_book
        tracker._tracking_message_queues["BTC-USDT"] = asyncio.Queue()

        # Create a diff message
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": "BTC-USDT",
                "update_id": 150,
                "bids": [],
                "asks": [],
            },
            timestamp=time.time(),
        )

        # Put message in the diff stream
        await tracker._order_book_diff_stream.put(diff_message)

        # Run router for a short time
        router_task = asyncio.create_task(tracker._order_book_diff_router())
        await asyncio.sleep(0.1)
        router_task.cancel()

        try:
            await router_task
        except asyncio.CancelledError:
            pass

        # Verify metrics were updated
        self.assertEqual(1, tracker.metrics.total_diffs_processed)
        self.assertIn("BTC-USDT", tracker.metrics.per_pair_metrics)
        self.assertEqual(1, tracker.metrics.per_pair_metrics["BTC-USDT"].diffs_processed)

    async def test_diff_router_tracks_rejected_messages(self):
        """Test that diff router tracks rejected messages."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()

        # Set up order book with high snapshot_uid=200 (will reject older messages)
        order_book = create_order_book_with_snapshot_uid(200)
        tracker._order_books["BTC-USDT"] = order_book
        tracker._tracking_message_queues["BTC-USDT"] = asyncio.Queue()

        # Create a diff message with update_id < snapshot_uid (will be rejected)
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": "BTC-USDT",
                "update_id": 150,  # Less than snapshot_uid of 200
                "bids": [],
                "asks": [],
            },
            timestamp=time.time(),
        )

        await tracker._order_book_diff_stream.put(diff_message)

        router_task = asyncio.create_task(tracker._order_book_diff_router())
        await asyncio.sleep(0.1)
        router_task.cancel()

        try:
            await router_task
        except asyncio.CancelledError:
            pass

        # Verify rejection was tracked
        self.assertEqual(1, tracker.metrics.total_diffs_rejected)
        self.assertEqual(1, tracker.metrics.per_pair_metrics["BTC-USDT"].diffs_rejected)

    async def test_diff_router_tracks_queued_messages(self):
        """Test that diff router tracks queued messages for unknown pairs."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()

        # Don't set up tracking queue - message should be queued
        diff_message = OrderBookMessage(
            message_type=OrderBookMessageType.DIFF,
            content={
                "trading_pair": "SOL-USDT",
                "update_id": 150,
                "bids": [],
                "asks": [],
            },
            timestamp=time.time(),
        )

        await tracker._order_book_diff_stream.put(diff_message)

        router_task = asyncio.create_task(tracker._order_book_diff_router())
        await asyncio.sleep(0.1)
        router_task.cancel()

        try:
            await router_task
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, tracker.metrics.total_diffs_queued)

    async def test_snapshot_router_updates_metrics(self):
        """Test that snapshot router updates metrics."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()
        tracker._tracking_message_queues["BTC-USDT"] = asyncio.Queue()

        snapshot_message = OrderBookMessage(
            message_type=OrderBookMessageType.SNAPSHOT,
            content={
                "trading_pair": "BTC-USDT",
                "update_id": 100,
                "bids": [],
                "asks": [],
            },
            timestamp=time.time(),
        )

        await tracker._order_book_snapshot_stream.put(snapshot_message)

        router_task = asyncio.create_task(tracker._order_book_snapshot_router())
        await asyncio.sleep(0.1)
        router_task.cancel()

        try:
            await router_task
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, tracker.metrics.total_snapshots_processed)

    async def test_trade_event_loop_updates_metrics(self):
        """Test that trade event loop updates metrics."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        # Set up order book
        tracker._order_books["BTC-USDT"] = OrderBook()

        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": "BTC-USDT",
                "trade_id": 12345,
                "price": "50000.0",
                "amount": "1.0",
                "trade_type": 1.0,  # BUY
            },
            timestamp=time.time(),
        )

        await tracker._order_book_trade_stream.put(trade_message)

        trade_task = asyncio.create_task(tracker._emit_trade_event_loop())
        await asyncio.sleep(0.1)
        trade_task.cancel()

        try:
            await trade_task
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, tracker.metrics.total_trades_processed)

    async def test_trade_event_loop_tracks_rejected_trades(self):
        """Test that trade event loop tracks rejected trades."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        # Don't set up order book - trade should be rejected
        trade_message = OrderBookMessage(
            message_type=OrderBookMessageType.TRADE,
            content={
                "trading_pair": "UNKNOWN-PAIR",
                "trade_id": 12345,
                "price": "50000.0",
                "amount": "1.0",
                "trade_type": 1.0,
            },
            timestamp=time.time(),
        )

        await tracker._order_book_trade_stream.put(trade_message)

        trade_task = asyncio.create_task(tracker._emit_trade_event_loop())
        await asyncio.sleep(0.1)
        trade_task.cancel()

        try:
            await trade_task
        except asyncio.CancelledError:
            pass

        self.assertEqual(1, tracker.metrics.total_trades_rejected)

    async def test_remove_trading_pair_cleans_up_metrics(self):
        """Test that removing a trading pair cleans up its metrics."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        # Set up a trading pair
        tracker._order_books["SOL-USDT"] = OrderBook()
        tracker._tracking_message_queues["SOL-USDT"] = asyncio.Queue()
        tracker._trading_pairs.append("SOL-USDT")

        # Create metrics for this pair
        pair_metrics = tracker.metrics.get_or_create_pair_metrics("SOL-USDT")
        pair_metrics.diffs_processed = 100

        self.assertIn("SOL-USDT", tracker.metrics.per_pair_metrics)

        # Mock unsubscribe
        self.data_source.unsubscribe_from_trading_pair = AsyncMock(return_value=True)

        # Remove the pair
        result = await tracker.remove_trading_pair("SOL-USDT")

        self.assertTrue(result)
        self.assertNotIn("SOL-USDT", tracker.metrics.per_pair_metrics)


class OrderBookTrackerDynamicPairTests(IsolatedAsyncioWrapperTestCase):
    """Tests for dynamically adding/removing trading pairs from OrderBookTracker."""

    def setUp(self):
        super().setUp()
        self.data_source = MagicMock(spec=OrderBookTrackerDataSource)
        self.trading_pairs = ["BTC-USDT", "ETH-USDT"]

    def _create_tracker(self):
        """Create a tracker instance for testing."""
        return OrderBookTracker(
            data_source=self.data_source,
            trading_pairs=self.trading_pairs,
        )

    async def test_add_trading_pair_successful(self):
        """Test successfully adding a new trading pair."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        new_pair = "SOL-USDT"

        # Mock data source methods
        self.data_source.subscribe_to_trading_pair = AsyncMock(return_value=True)
        self.data_source.get_new_order_book = AsyncMock(return_value=OrderBook())

        result = await tracker.add_trading_pair(new_pair)

        self.assertTrue(result)
        self.assertIn(new_pair, tracker._order_books)
        self.assertIn(new_pair, tracker._tracking_message_queues)
        self.assertIn(new_pair, tracker._tracking_tasks)
        self.assertIn(new_pair, tracker._trading_pairs)
        self.data_source.subscribe_to_trading_pair.assert_called_once_with(new_pair)

        # Clean up tracking task
        tracker._tracking_tasks[new_pair].cancel()

    async def test_add_trading_pair_already_tracked(self):
        """Test that adding an already tracked pair returns False."""
        tracker = self._create_tracker()
        tracker._order_books_initialized.set()

        # Add order book for existing pair
        existing_pair = "BTC-USDT"
        tracker._order_books[existing_pair] = OrderBook()

        result = await tracker.add_trading_pair(existing_pair)

        self.assertFalse(result)
        self.data_source.subscribe_to_trading_pair.assert_not_called()

    async def test_add_trading_pair_subscription_fails(self):
        """Test that failed subscription returns False."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        new_pair = "SOL-USDT"

        # Mock subscription to fail
        self.data_source.subscribe_to_trading_pair = AsyncMock(return_value=False)

        result = await tracker.add_trading_pair(new_pair)

        self.assertFalse(result)
        self.assertNotIn(new_pair, tracker._order_books)

    async def test_add_trading_pair_waits_for_initialization(self):
        """Test that add_trading_pair waits for initialization before proceeding."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()

        new_pair = "SOL-USDT"

        # Mock data source methods
        self.data_source.subscribe_to_trading_pair = AsyncMock(return_value=True)
        self.data_source.get_new_order_book = AsyncMock(return_value=OrderBook())

        # Start add_trading_pair (will wait for initialization)
        add_task = asyncio.create_task(tracker.add_trading_pair(new_pair))

        # Let it start waiting
        await asyncio.sleep(0.01)

        # Verify it hasn't subscribed yet
        self.data_source.subscribe_to_trading_pair.assert_not_called()

        # Set initialized
        tracker._order_books_initialized.set()

        # Now it should complete
        result = await add_task

        self.assertTrue(result)
        self.data_source.subscribe_to_trading_pair.assert_called_once()

        # Clean up
        tracker._tracking_tasks[new_pair].cancel()

    async def test_add_trading_pair_exception_cleanup(self):
        """Test that exceptions during add clean up partial state."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        new_pair = "SOL-USDT"

        # Mock subscribe to succeed but get_new_order_book to fail
        self.data_source.subscribe_to_trading_pair = AsyncMock(return_value=True)
        self.data_source.get_new_order_book = AsyncMock(side_effect=Exception("Test Error"))

        result = await tracker.add_trading_pair(new_pair)

        self.assertFalse(result)
        # Verify cleanup happened
        self.assertNotIn(new_pair, tracker._order_books)
        self.assertNotIn(new_pair, tracker._tracking_message_queues)
        self.assertNotIn(new_pair, tracker._tracking_tasks)

    async def test_add_trading_pair_raises_cancel_exception(self):
        """Test that CancelledError is properly propagated."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        new_pair = "SOL-USDT"

        # Mock subscribe to raise CancelledError
        self.data_source.subscribe_to_trading_pair = AsyncMock(side_effect=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            await tracker.add_trading_pair(new_pair)

    async def test_remove_trading_pair_successful(self):
        """Test successfully removing a trading pair."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        # Set up a trading pair to remove
        pair_to_remove = "SOL-USDT"
        tracker._order_books[pair_to_remove] = OrderBook()
        tracker._tracking_message_queues[pair_to_remove] = asyncio.Queue()
        tracker._trading_pairs.append(pair_to_remove)

        # Create a mock tracking task
        async def mock_tracking():
            await asyncio.sleep(100)

        tracker._tracking_tasks[pair_to_remove] = asyncio.create_task(mock_tracking())

        # Create metrics for this pair
        tracker.metrics.get_or_create_pair_metrics(pair_to_remove)

        # Mock unsubscribe
        self.data_source.unsubscribe_from_trading_pair = AsyncMock(return_value=True)

        result = await tracker.remove_trading_pair(pair_to_remove)

        self.assertTrue(result)
        self.assertNotIn(pair_to_remove, tracker._order_books)
        self.assertNotIn(pair_to_remove, tracker._tracking_message_queues)
        self.assertNotIn(pair_to_remove, tracker._tracking_tasks)
        self.assertNotIn(pair_to_remove, tracker._trading_pairs)
        self.assertNotIn(pair_to_remove, tracker.metrics.per_pair_metrics)
        self.data_source.unsubscribe_from_trading_pair.assert_called_once_with(pair_to_remove)

    async def test_remove_trading_pair_not_tracked(self):
        """Test that removing a non-tracked pair returns False."""
        tracker = self._create_tracker()

        result = await tracker.remove_trading_pair("NONEXISTENT-PAIR")

        self.assertFalse(result)
        self.data_source.unsubscribe_from_trading_pair.assert_not_called()

    async def test_remove_trading_pair_unsubscribe_fails_continues_cleanup(self):
        """Test that cleanup continues even if unsubscribe fails."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()
        tracker._order_books_initialized.set()

        # Set up a trading pair to remove
        pair_to_remove = "SOL-USDT"
        tracker._order_books[pair_to_remove] = OrderBook()
        tracker._tracking_message_queues[pair_to_remove] = asyncio.Queue()
        tracker._trading_pairs.append(pair_to_remove)

        # Mock unsubscribe to fail
        self.data_source.unsubscribe_from_trading_pair = AsyncMock(return_value=False)

        result = await tracker.remove_trading_pair(pair_to_remove)

        # Should still return True as cleanup was done
        self.assertTrue(result)
        self.assertNotIn(pair_to_remove, tracker._order_books)

    async def test_remove_trading_pair_raises_cancel_exception(self):
        """Test that CancelledError is properly propagated during removal."""
        tracker = self._create_tracker()
        tracker._order_books["SOL-USDT"] = OrderBook()

        # Mock unsubscribe to raise CancelledError
        self.data_source.unsubscribe_from_trading_pair = AsyncMock(side_effect=asyncio.CancelledError)

        with self.assertRaises(asyncio.CancelledError):
            await tracker.remove_trading_pair("SOL-USDT")

    async def test_remove_trading_pair_exception_returns_false(self):
        """Test that exceptions during removal return False."""
        tracker = self._create_tracker()
        tracker._order_books["SOL-USDT"] = OrderBook()
        tracker._tracking_message_queues["SOL-USDT"] = asyncio.Queue()

        # Mock unsubscribe to raise exception
        self.data_source.unsubscribe_from_trading_pair = AsyncMock(side_effect=Exception("Test Error"))

        result = await tracker.remove_trading_pair("SOL-USDT")

        self.assertFalse(result)

    async def test_remove_trading_pair_cleans_up_past_diffs_and_saved_messages(self):
        """Test that removal cleans up past diffs windows and saved message queues."""
        tracker = self._create_tracker()
        tracker._metrics.tracker_start_time = time.perf_counter()

        pair_to_remove = "SOL-USDT"
        tracker._order_books[pair_to_remove] = OrderBook()
        tracker._tracking_message_queues[pair_to_remove] = asyncio.Queue()
        tracker._trading_pairs.append(pair_to_remove)

        # Add some past diffs and saved messages
        tracker._past_diffs_windows[pair_to_remove].append("test_diff")
        tracker._saved_message_queues[pair_to_remove].append("test_message")

        self.data_source.unsubscribe_from_trading_pair = AsyncMock(return_value=True)

        result = await tracker.remove_trading_pair(pair_to_remove)

        self.assertTrue(result)
        self.assertNotIn(pair_to_remove, tracker._past_diffs_windows)
        self.assertNotIn(pair_to_remove, tracker._saved_message_queues)


class LatencyStatsEdgeCasesTests(unittest.TestCase):
    """Edge case tests for LatencyStats."""

    def test_very_small_latencies(self):
        """Test handling of very small latency values."""
        stats = LatencyStats()
        stats.SAMPLE_RATE = 1

        stats.record(0.001)
        stats.record(0.0001)

        self.assertEqual(0.0001, stats.min_ms)

    def test_very_large_latencies(self):
        """Test handling of very large latency values."""
        stats = LatencyStats()
        stats.SAMPLE_RATE = 1

        stats.record(10000.0)
        stats.record(100000.0)

        self.assertEqual(100000.0, stats.max_ms)

    def test_negative_latency_handling(self):
        """Test that negative latencies are handled (though shouldn't occur)."""
        stats = LatencyStats()
        stats.SAMPLE_RATE = 1

        stats.record(-1.0)  # Shouldn't happen but shouldn't crash

        self.assertEqual(-1.0, stats.min_ms)
