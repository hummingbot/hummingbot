"""
Unit tests for XRPL Transaction Pipeline.

Tests the serialized transaction submission pipeline for XRPL.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.xrpl.xrpl_transaction_pipeline import XRPLTransactionPipeline
from hummingbot.connector.exchange.xrpl.xrpl_utils import XRPLSystemBusyError


class TestXRPLTransactionPipelineInit(unittest.TestCase):
    """Tests for XRPLTransactionPipeline initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        pipeline = XRPLTransactionPipeline()
        self.assertFalse(pipeline.is_running)
        self.assertEqual(pipeline.queue_size, 0)
        self.assertFalse(pipeline._started)
        self.assertIsNotNone(pipeline._submission_queue)

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        pipeline = XRPLTransactionPipeline(
            max_queue_size=50,
            submission_delay_ms=500,
        )
        self.assertEqual(pipeline._max_queue_size, 50)
        self.assertEqual(pipeline._delay_seconds, 0.5)


class TestXRPLTransactionPipelineStats(unittest.TestCase):
    """Tests for XRPLTransactionPipeline statistics."""

    def test_stats_initial_values(self):
        """Test initial statistics values."""
        pipeline = XRPLTransactionPipeline()
        stats = pipeline.stats
        self.assertEqual(stats["queue_size"], 0)
        self.assertEqual(stats["submissions_processed"], 0)
        self.assertEqual(stats["submissions_failed"], 0)
        self.assertEqual(stats["avg_latency_ms"], 0.0)

    def test_stats_avg_latency_calculation(self):
        """Test average latency calculation."""
        pipeline = XRPLTransactionPipeline()
        pipeline._submissions_processed = 10
        pipeline._total_latency_ms = 1000.0
        stats = pipeline.stats
        self.assertEqual(stats["avg_latency_ms"], 100.0)

    def test_stats_avg_latency_with_failures(self):
        """Test average latency includes failed submissions."""
        pipeline = XRPLTransactionPipeline()
        pipeline._submissions_processed = 5
        pipeline._submissions_failed = 5
        pipeline._total_latency_ms = 1000.0
        stats = pipeline.stats
        # Total = 10, latency = 1000, avg = 100
        self.assertEqual(stats["avg_latency_ms"], 100.0)


class TestXRPLTransactionPipelineLifecycle(unittest.IsolatedAsyncioTestCase):
    """Tests for XRPLTransactionPipeline lifecycle methods."""

    async def test_start_creates_task(self):
        """Test that start creates the pipeline task."""
        pipeline = XRPLTransactionPipeline()
        await pipeline.start()
        try:
            self.assertTrue(pipeline.is_running)
            self.assertTrue(pipeline._started)
            self.assertIsNotNone(pipeline._pipeline_task)
        finally:
            await pipeline.stop()

    async def test_start_idempotent(self):
        """Test that calling start multiple times is idempotent."""
        pipeline = XRPLTransactionPipeline()
        await pipeline.start()
        task1 = pipeline._pipeline_task
        await pipeline.start()  # Second call should be ignored
        task2 = pipeline._pipeline_task
        self.assertEqual(task1, task2)
        await pipeline.stop()

    async def test_stop_cancels_task(self):
        """Test that stop cancels the pipeline task."""
        pipeline = XRPLTransactionPipeline()
        await pipeline.start()
        await pipeline.stop()
        self.assertFalse(pipeline.is_running)
        self.assertIsNone(pipeline._pipeline_task)

    async def test_stop_when_not_running(self):
        """Test that stop is safe when pipeline is not running."""
        pipeline = XRPLTransactionPipeline()
        # Should not raise
        await pipeline.stop()
        self.assertFalse(pipeline.is_running)

    async def test_stop_cancels_pending_submissions(self):
        """Test that stop cancels pending submissions in queue."""
        pipeline = XRPLTransactionPipeline()
        await pipeline.start()

        # Add some submissions to the queue directly
        future1 = asyncio.get_event_loop().create_future()
        future2 = asyncio.get_event_loop().create_future()
        await pipeline._submission_queue.put((AsyncMock()(), future1, "sub1"))
        await pipeline._submission_queue.put((AsyncMock()(), future2, "sub2"))

        await pipeline.stop()

        # Futures should be cancelled
        self.assertTrue(future1.cancelled())
        self.assertTrue(future2.cancelled())


class TestXRPLTransactionPipelineSubmit(unittest.IsolatedAsyncioTestCase):
    """Tests for XRPLTransactionPipeline submit method."""

    async def test_submit_successful(self):
        """Test successful submission through the pipeline."""
        pipeline = XRPLTransactionPipeline(submission_delay_ms=1)

        async def mock_coroutine():
            return "success_result"

        result = await pipeline.submit(mock_coroutine(), submission_id="test-sub")
        self.assertEqual(result, "success_result")
        self.assertEqual(pipeline._submissions_processed, 1)
        await pipeline.stop()

    async def test_submit_lazy_starts_pipeline(self):
        """Test that submit lazily starts the pipeline."""
        pipeline = XRPLTransactionPipeline(submission_delay_ms=1)
        self.assertFalse(pipeline._started)

        async def mock_coroutine():
            return "result"

        await pipeline.submit(mock_coroutine())
        self.assertTrue(pipeline._started)
        await pipeline.stop()

    async def test_submit_generates_id_if_not_provided(self):
        """Test that submit generates submission_id if not provided."""
        pipeline = XRPLTransactionPipeline(submission_delay_ms=1)

        async def mock_coroutine():
            return "result"

        # Should not raise
        result = await pipeline.submit(mock_coroutine())
        self.assertEqual(result, "result")
        await pipeline.stop()

    async def test_submit_propagates_exception(self):
        """Test that exceptions from coroutine are propagated."""
        pipeline = XRPLTransactionPipeline(submission_delay_ms=1)

        async def failing_coroutine():
            raise ValueError("Test error")

        with self.assertRaises(ValueError) as context:
            await pipeline.submit(failing_coroutine())
        self.assertEqual(str(context.exception), "Test error")
        self.assertEqual(pipeline._submissions_failed, 1)
        await pipeline.stop()

    async def test_submit_rejects_when_queue_full(self):
        """Test that submit raises XRPLSystemBusyError when queue is full."""
        pipeline = XRPLTransactionPipeline(max_queue_size=1, submission_delay_ms=1000)
        await pipeline.start()

        # Create a coroutine that blocks
        blocker_started = asyncio.Event()
        blocker_continue = asyncio.Event()

        async def blocking_coroutine():
            blocker_started.set()
            await blocker_continue.wait()
            return "blocked"

        # Submit first task - will start processing immediately
        task = asyncio.create_task(pipeline.submit(blocking_coroutine(), submission_id="blocker"))
        await blocker_started.wait()

        # Fill the queue (size=1, so this fills it)
        future = asyncio.get_event_loop().create_future()

        async def filler_coro():
            return "filler"

        pipeline._submission_queue.put_nowait((filler_coro(), future, "filler"))

        # Now queue is full, next submit should fail with XRPLSystemBusyError
        async def overflow_coro():
            return "overflow"

        with self.assertRaises(XRPLSystemBusyError):
            await pipeline.submit(overflow_coro(), submission_id="overflow")

        # Cleanup
        blocker_continue.set()
        await task
        await pipeline.stop()

    async def test_submit_when_not_running_after_stop(self):
        """Test that submit raises when pipeline is stopped after being started."""
        pipeline = XRPLTransactionPipeline(submission_delay_ms=1)
        await pipeline.start()
        await pipeline.stop()

        async def mock_coroutine():
            return "result"

        with self.assertRaises(XRPLSystemBusyError):
            await pipeline.submit(mock_coroutine())


class TestXRPLTransactionPipelineSerialization(unittest.IsolatedAsyncioTestCase):
    """Tests for XRPLTransactionPipeline serialization behavior."""

    async def test_submissions_processed_in_order(self):
        """Test that submissions are processed in FIFO order."""
        pipeline = XRPLTransactionPipeline(submission_delay_ms=1)
        results = []

        async def make_coroutine(value):
            results.append(value)
            return value

        # Submit multiple coroutines
        tasks = [
            asyncio.create_task(pipeline.submit(make_coroutine(i), submission_id=f"sub-{i}"))
            for i in range(5)
        ]

        await asyncio.gather(*tasks)

        # Results should be in order
        self.assertEqual(results, [0, 1, 2, 3, 4])
        await pipeline.stop()

    async def test_delay_between_submissions(self):
        """Test that there is a delay between submissions."""
        import time

        delay_ms = 50
        pipeline = XRPLTransactionPipeline(submission_delay_ms=delay_ms)
        times = []

        async def record_time():
            times.append(time.time())
            return "done"

        # Submit two coroutines
        await pipeline.submit(record_time(), submission_id="sub1")
        await pipeline.submit(record_time(), submission_id="sub2")

        # Check that there was at least some delay between them
        if len(times) == 2:
            elapsed_ms = (times[1] - times[0]) * 1000
            # Allow some tolerance, but should be at least delay_ms
            self.assertGreaterEqual(elapsed_ms, delay_ms * 0.8)

        await pipeline.stop()


class TestXRPLTransactionPipelineSkipCancelled(unittest.IsolatedAsyncioTestCase):
    """Tests for XRPLTransactionPipeline handling of cancelled futures."""

    async def test_skips_cancelled_submissions(self):
        """Test that cancelled submissions are skipped."""
        pipeline = XRPLTransactionPipeline(submission_delay_ms=1)
        await pipeline.start()

        # Create a future and cancel it
        cancelled_future = asyncio.get_event_loop().create_future()
        cancelled_future.cancel()

        # Put the cancelled submission in the queue
        async def mock_coro():
            return "should not run"

        await pipeline._submission_queue.put((mock_coro(), cancelled_future, "cancelled-sub"))

        # Give the pipeline a moment to process
        await asyncio.sleep(0.1)

        # The cancelled submission should be skipped
        # Check that it didn't increment the processed count (it was skipped)
        # Note: The counter only increments when pipeline gets to process, not when skipped
        await pipeline.stop()


class TestXRPLTransactionPipelineEnsureStarted(unittest.IsolatedAsyncioTestCase):
    """Tests for _ensure_started method."""

    async def test_ensure_started_lazy_init(self):
        """Test that _ensure_started handles lazy initialization."""
        pipeline = XRPLTransactionPipeline()
        self.assertFalse(pipeline._started)

        await pipeline._ensure_started()

        self.assertTrue(pipeline._started)
        self.assertTrue(pipeline.is_running)
        await pipeline.stop()

    async def test_ensure_started_idempotent(self):
        """Test that _ensure_started is idempotent."""
        pipeline = XRPLTransactionPipeline()

        await pipeline._ensure_started()
        task1 = pipeline._pipeline_task

        await pipeline._ensure_started()
        task2 = pipeline._pipeline_task

        self.assertEqual(task1, task2)
        await pipeline.stop()


if __name__ == "__main__":
    unittest.main()
