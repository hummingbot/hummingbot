"""
Unit tests for XRPL Worker Pool Module.

Tests the worker pools and their result dataclasses.
"""
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.models import AccountInfo, Response

from hummingbot.connector.exchange.xrpl.xrpl_utils import XRPLConnectionError
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import (
    PoolStats,
    QueryResult,
    TransactionSubmitResult,
    TransactionVerifyResult,
    WorkerTask,
    XRPLQueryWorkerPool,
    XRPLVerificationWorkerPool,
)


class TestTransactionSubmitResult(unittest.TestCase):
    """Tests for TransactionSubmitResult dataclass."""

    def test_is_queued_true(self):
        """Test is_queued returns True for terQUEUED."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="terQUEUED",
        )
        self.assertTrue(result.is_queued)

    def test_is_queued_false(self):
        """Test is_queued returns False for other results."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="tesSUCCESS",
        )
        self.assertFalse(result.is_queued)

    def test_is_accepted_tesSUCCESS(self):
        """Test is_accepted returns True for tesSUCCESS."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="tesSUCCESS",
        )
        self.assertTrue(result.is_accepted)

    def test_is_accepted_terQUEUED(self):
        """Test is_accepted returns True for terQUEUED."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="terQUEUED",
        )
        self.assertTrue(result.is_accepted)

    def test_is_accepted_false(self):
        """Test is_accepted returns False for failure results."""
        result = TransactionSubmitResult(
            success=False,
            prelim_result="tefPAST_SEQ",
        )
        self.assertFalse(result.is_accepted)

    def test_all_fields(self):
        """Test all fields can be set."""
        mock_tx = MagicMock()
        mock_response = MagicMock()
        result = TransactionSubmitResult(
            success=True,
            signed_tx=mock_tx,
            response=mock_response,
            prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890-ABC",
            error=None,
            tx_hash="ABCDEF123456",
        )
        self.assertTrue(result.success)
        self.assertEqual(result.signed_tx, mock_tx)
        self.assertEqual(result.response, mock_response)
        self.assertEqual(result.prelim_result, "tesSUCCESS")
        self.assertEqual(result.exchange_order_id, "12345-67890-ABC")
        self.assertIsNone(result.error)
        self.assertEqual(result.tx_hash, "ABCDEF123456")


class TestTransactionVerifyResult(unittest.TestCase):
    """Tests for TransactionVerifyResult dataclass."""

    def test_verified_true(self):
        """Test verified result."""
        result = TransactionVerifyResult(
            verified=True,
            response=MagicMock(),
            final_result="tesSUCCESS",
        )
        self.assertTrue(result.verified)
        self.assertEqual(result.final_result, "tesSUCCESS")

    def test_verified_false(self):
        """Test failed verification result."""
        result = TransactionVerifyResult(
            verified=False,
            error="Transaction not found",
        )
        self.assertFalse(result.verified)
        self.assertEqual(result.error, "Transaction not found")


class TestQueryResult(unittest.TestCase):
    """Tests for QueryResult dataclass."""

    def test_success_result(self):
        """Test successful query result."""
        mock_response = MagicMock()
        result = QueryResult(
            success=True,
            response=mock_response,
        )
        self.assertTrue(result.success)
        self.assertEqual(result.response, mock_response)
        self.assertIsNone(result.error)

    def test_failure_result(self):
        """Test failed query result."""
        result = QueryResult(
            success=False,
            error="Request timed out",
        )
        self.assertFalse(result.success)
        self.assertIsNone(result.response)
        self.assertEqual(result.error, "Request timed out")


class TestWorkerTask(unittest.TestCase):
    """Tests for WorkerTask dataclass."""

    def test_task_creation(self):
        """Test creating a worker task."""
        # Use a MagicMock for future since we don't need real async behavior
        mock_future = MagicMock()
        task = WorkerTask(
            task_id="test-123",
            request=MagicMock(),
            future=mock_future,
            timeout=30.0,
        )
        self.assertEqual(task.task_id, "test-123")
        self.assertFalse(task.is_expired)

    def test_is_expired_false(self):
        """Test is_expired returns False for fresh task."""
        mock_future = MagicMock()
        task = WorkerTask(
            task_id="test-123",
            request=MagicMock(),
            future=mock_future,
            max_queue_time=60.0,
        )
        self.assertFalse(task.is_expired)

    def test_is_expired_true(self):
        """Test is_expired returns True for old task."""
        mock_future = MagicMock()
        task = WorkerTask(
            task_id="test-123",
            request=MagicMock(),
            future=mock_future,
            max_queue_time=0.0,  # Immediate expiry
        )
        # Small delay to ensure time passes
        time.sleep(0.01)
        self.assertTrue(task.is_expired)


class TestPoolStats(unittest.TestCase):
    """Tests for PoolStats dataclass."""

    def test_initial_stats(self):
        """Test initial pool statistics."""
        stats = PoolStats(pool_name="TestPool", num_workers=5)
        self.assertEqual(stats.pool_name, "TestPool")
        self.assertEqual(stats.num_workers, 5)
        self.assertEqual(stats.tasks_completed, 0)
        self.assertEqual(stats.tasks_failed, 0)
        self.assertEqual(stats.tasks_pending, 0)
        self.assertEqual(stats.avg_latency_ms, 0.0)

    def test_avg_latency_calculation(self):
        """Test average latency calculation."""
        stats = PoolStats(pool_name="TestPool", num_workers=5)
        stats.tasks_completed = 10
        stats.tasks_failed = 5
        stats.total_latency_ms = 1500.0
        # (10 + 5) = 15 total tasks, 1500 / 15 = 100
        self.assertEqual(stats.avg_latency_ms, 100.0)

    def test_avg_latency_zero_tasks(self):
        """Test average latency with no tasks."""
        stats = PoolStats(pool_name="TestPool", num_workers=5)
        self.assertEqual(stats.avg_latency_ms, 0.0)

    def test_to_dict(self):
        """Test converting stats to dictionary."""
        stats = PoolStats(pool_name="TestPool", num_workers=5)
        stats.tasks_completed = 10
        stats.tasks_failed = 2
        stats.tasks_pending = 3
        stats.total_latency_ms = 1200.0
        stats.client_reconnects = 1
        stats.client_failures = 0

        d = stats.to_dict()
        self.assertEqual(d["pool_name"], "TestPool")
        self.assertEqual(d["num_workers"], 5)
        self.assertEqual(d["tasks_completed"], 10)
        self.assertEqual(d["tasks_failed"], 2)
        self.assertEqual(d["tasks_pending"], 3)
        self.assertEqual(d["avg_latency_ms"], 100.0)
        self.assertEqual(d["client_reconnects"], 1)
        self.assertEqual(d["client_failures"], 0)


class TestXRPLQueryWorkerPool(unittest.IsolatedAsyncioTestCase):
    """Tests for XRPLQueryWorkerPool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_node_pool = MagicMock()
        self.mock_client = MagicMock()
        self.mock_node_pool.get_client = AsyncMock(return_value=self.mock_client)

    async def test_init(self):
        """Test pool initialization."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=3)
        self.assertEqual(pool._pool_name, "QueryPool")
        self.assertEqual(pool._num_workers, 3)
        self.assertFalse(pool.is_running)

    async def test_start_and_stop(self):
        """Test starting and stopping the pool."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=2)
        await pool.start()
        self.assertTrue(pool.is_running)
        self.assertEqual(len(pool._worker_tasks), 2)

        await pool.stop()
        self.assertFalse(pool.is_running)
        self.assertEqual(len(pool._worker_tasks), 0)

    async def test_submit_successful_query(self):
        """Test submitting a successful query."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=1)

        # Mock successful response
        mock_response = MagicMock(spec=Response)
        mock_response.is_successful.return_value = True
        mock_response.result = {"account": "rXXX", "balance": "1000000"}
        self.mock_client._request_impl = AsyncMock(return_value=mock_response)

        request = AccountInfo(account="rXXX")
        result = await pool.submit(request)

        self.assertIsInstance(result, QueryResult)
        self.assertTrue(result.success)
        self.assertEqual(result.response, mock_response)
        self.assertIsNone(result.error)

        await pool.stop()

    async def test_submit_failed_query(self):
        """Test submitting a query that returns an error."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=1)

        # Mock error response
        mock_response = MagicMock(spec=Response)
        mock_response.is_successful.return_value = False
        mock_response.result = {"error": "actNotFound", "error_message": "Account not found"}
        self.mock_client._request_impl = AsyncMock(return_value=mock_response)

        request = AccountInfo(account="rInvalidXXX")
        result = await pool.submit(request)

        self.assertIsInstance(result, QueryResult)
        self.assertFalse(result.success)
        self.assertEqual(result.response, mock_response)
        self.assertIn("actNotFound", result.error)

        await pool.stop()

    async def test_stats_tracking(self):
        """Test that statistics are tracked correctly."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=1)

        # Mock successful response
        mock_response = MagicMock(spec=Response)
        mock_response.is_successful.return_value = True
        mock_response.result = {}
        self.mock_client._request_impl = AsyncMock(return_value=mock_response)

        request = AccountInfo(account="rXXX")
        await pool.submit(request)
        await pool.submit(request)

        stats = pool.stats
        self.assertEqual(stats.tasks_completed, 2)

        await pool.stop()

    async def test_lazy_initialization(self):
        """Test that pool starts lazily on first submit."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=1)
        self.assertFalse(pool._started)

        # Mock successful response
        mock_response = MagicMock(spec=Response)
        mock_response.is_successful.return_value = True
        mock_response.result = {}
        self.mock_client._request_impl = AsyncMock(return_value=mock_response)

        request = AccountInfo(account="rXXX")
        await pool.submit(request)

        self.assertTrue(pool._started)
        self.assertTrue(pool.is_running)

        await pool.stop()


class TestXRPLVerificationWorkerPool(unittest.IsolatedAsyncioTestCase):
    """Tests for XRPLVerificationWorkerPool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_node_pool = MagicMock()
        self.mock_client = MagicMock()
        self.mock_node_pool.get_client = AsyncMock(return_value=self.mock_client)

    async def test_init(self):
        """Test pool initialization."""
        pool = XRPLVerificationWorkerPool(self.mock_node_pool, num_workers=2)
        self.assertEqual(pool._pool_name, "VerifyPool")
        self.assertEqual(pool._num_workers, 2)

    async def test_submit_verification_invalid_prelim_result(self):
        """Test verification with invalid preliminary result."""
        pool = XRPLVerificationWorkerPool(self.mock_node_pool, num_workers=1)

        mock_signed_tx = MagicMock()
        mock_signed_tx.get_hash.return_value = "ABC123DEF456"

        result = await pool.submit_verification(
            signed_tx=mock_signed_tx,
            prelim_result="tefPAST_SEQ",  # Invalid prelim result
            timeout=5.0,
        )

        self.assertIsInstance(result, TransactionVerifyResult)
        self.assertFalse(result.verified)
        self.assertIn("indicates failure", result.error)

        await pool.stop()

    async def test_submit_verification_success(self):
        """Test successful transaction verification."""
        pool = XRPLVerificationWorkerPool(self.mock_node_pool, num_workers=1)

        mock_signed_tx = MagicMock()
        mock_signed_tx.get_hash.return_value = "ABC123DEF456"
        mock_signed_tx.last_ledger_sequence = 12345

        # Mock the wait_for_final_transaction_outcome function
        mock_response = MagicMock(spec=Response)
        mock_response.result = {"meta": {"TransactionResult": "tesSUCCESS"}}

        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_worker_pool._wait_for_final_transaction_outcome",
            new_callable=AsyncMock,
        ) as mock_wait:
            mock_wait.return_value = mock_response

            result = await pool.submit_verification(
                signed_tx=mock_signed_tx,
                prelim_result="tesSUCCESS",
                timeout=5.0,
            )

        self.assertIsInstance(result, TransactionVerifyResult)
        self.assertTrue(result.verified)
        self.assertEqual(result.final_result, "tesSUCCESS")

        await pool.stop()


class TestWorkerPoolBase(unittest.IsolatedAsyncioTestCase):
    """Tests for XRPLWorkerPoolBase abstract class."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_node_pool = MagicMock()
        self.mock_client = MagicMock()
        self.mock_node_pool.get_client = AsyncMock(return_value=self.mock_client)

    async def test_start_idempotent(self):
        """Test that start is idempotent."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=2)
        await pool.start()
        task_count = len(pool._worker_tasks)

        await pool.start()  # Second call should be ignored
        self.assertEqual(len(pool._worker_tasks), task_count)

        await pool.stop()

    async def test_stop_idempotent(self):
        """Test that stop is idempotent."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=2)
        await pool.start()
        await pool.stop()
        await pool.stop()  # Second call should be safe
        self.assertFalse(pool.is_running)

    async def test_stats_property(self):
        """Test that stats property updates pending tasks."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=1)
        await pool.start()

        # The stats should reflect queue size
        stats = pool.stats
        self.assertEqual(stats.tasks_pending, 0)

        await pool.stop()

    async def test_connection_error_retry(self):
        """Test that connection errors trigger retry logic."""
        pool = XRPLQueryWorkerPool(self.mock_node_pool, num_workers=1)

        # First call raises connection error, second succeeds
        mock_response = MagicMock(spec=Response)
        mock_response.is_successful.return_value = True
        mock_response.result = {}

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise XRPLConnectionError("Connection lost")
            return mock_response

        self.mock_client._request_impl = mock_request
        self.mock_client.open = AsyncMock()

        request = AccountInfo(account="rXXX")
        result = await pool.submit(request, timeout=10.0)

        self.assertTrue(result.success)
        self.assertGreaterEqual(call_count, 2)

        await pool.stop()


if __name__ == "__main__":
    unittest.main()
