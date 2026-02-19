"""
Unit tests for XRPLWorkerPoolManager.

Tests the new pool-based architecture:
- RequestPriority constants
- Pool factory methods (lazy initialization)
- Lifecycle management (start/stop)
- Pipeline integration
"""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.xrpl.xrpl_utils import XRPLNodePool
from hummingbot.connector.exchange.xrpl.xrpl_worker_manager import RequestPriority, XRPLWorkerPoolManager


class TestRequestPriority(unittest.TestCase):
    """Tests for RequestPriority constants."""

    def test_priority_ordering(self):
        """Test priority values are correctly ordered."""
        self.assertLess(RequestPriority.LOW, RequestPriority.MEDIUM)
        self.assertLess(RequestPriority.MEDIUM, RequestPriority.HIGH)
        self.assertLess(RequestPriority.HIGH, RequestPriority.CRITICAL)

    def test_priority_values(self):
        """Test specific priority values."""
        self.assertEqual(RequestPriority.LOW, 1)
        self.assertEqual(RequestPriority.MEDIUM, 2)
        self.assertEqual(RequestPriority.HIGH, 3)
        self.assertEqual(RequestPriority.CRITICAL, 4)


class TestXRPLWorkerPoolManagerInit(unittest.TestCase):
    """Tests for XRPLWorkerPoolManager initialization."""

    def test_init_default_pool_sizes(self):
        """Test manager initializes with default pool sizes from constants."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        self.assertEqual(manager._node_pool, mock_node_pool)
        self.assertFalse(manager._running)
        self.assertIsNone(manager._query_pool)
        self.assertIsNone(manager._verification_pool)
        self.assertEqual(manager._transaction_pools, {})

    def test_init_custom_pool_sizes(self):
        """Test manager initializes with custom pool sizes."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(
            node_pool=mock_node_pool,
            query_pool_size=5,
            verification_pool_size=3,
            transaction_pool_size=2,
        )

        self.assertEqual(manager._query_pool_size, 5)
        self.assertEqual(manager._verification_pool_size, 3)
        self.assertEqual(manager._transaction_pool_size, 2)

    def test_node_pool_property(self):
        """Test node_pool property returns the node pool."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        self.assertEqual(manager.node_pool, mock_node_pool)

    def test_is_running_property(self):
        """Test is_running property."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        self.assertFalse(manager.is_running)
        manager._running = True
        self.assertTrue(manager.is_running)


class TestXRPLWorkerPoolManagerPipeline(unittest.TestCase):
    """Tests for pipeline property and lazy initialization."""

    def test_pipeline_lazy_initialization(self):
        """Test pipeline is lazily initialized."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        # Pipeline should be None initially
        self.assertIsNone(manager._pipeline)

        # Accessing property should create it
        pipeline = manager.pipeline
        self.assertIsNotNone(pipeline)
        self.assertIsNotNone(manager._pipeline)

    def test_pipeline_returns_same_instance(self):
        """Test pipeline property returns same instance."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        pipeline1 = manager.pipeline
        pipeline2 = manager.pipeline

        self.assertIs(pipeline1, pipeline2)

    def test_pipeline_queue_size_before_init(self):
        """Test pipeline_queue_size returns 0 before pipeline is created."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        self.assertEqual(manager.pipeline_queue_size, 0)


class TestXRPLWorkerPoolManagerPoolFactories(unittest.TestCase):
    """Tests for pool factory methods."""

    @patch('hummingbot.connector.exchange.xrpl.xrpl_worker_manager.XRPLQueryWorkerPool')
    def test_get_query_pool_lazy_init(self, mock_pool_class):
        """Test query pool is lazily initialized."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        manager = XRPLWorkerPoolManager(
            node_pool=mock_node_pool,
            query_pool_size=4,
        )

        # Pool should be None initially
        self.assertIsNone(manager._query_pool)

        # Get pool should create it
        pool = manager.get_query_pool()

        mock_pool_class.assert_called_once_with(
            node_pool=mock_node_pool,
            num_workers=4,
        )
        self.assertEqual(pool, mock_pool)

    @patch('hummingbot.connector.exchange.xrpl.xrpl_worker_manager.XRPLQueryWorkerPool')
    def test_get_query_pool_returns_same_instance(self, mock_pool_class):
        """Test get_query_pool returns the same instance."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        pool1 = manager.get_query_pool()
        pool2 = manager.get_query_pool()

        self.assertIs(pool1, pool2)
        # Should only be called once
        mock_pool_class.assert_called_once()

    @patch('hummingbot.connector.exchange.xrpl.xrpl_worker_manager.XRPLVerificationWorkerPool')
    def test_get_verification_pool_lazy_init(self, mock_pool_class):
        """Test verification pool is lazily initialized."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        manager = XRPLWorkerPoolManager(
            node_pool=mock_node_pool,
            verification_pool_size=3,
        )

        pool = manager.get_verification_pool()

        mock_pool_class.assert_called_once_with(
            node_pool=mock_node_pool,
            num_workers=3,
        )
        self.assertEqual(pool, mock_pool)

    @patch('hummingbot.connector.exchange.xrpl.xrpl_worker_manager.XRPLTransactionWorkerPool')
    def test_get_transaction_pool_creates_per_wallet(self, mock_pool_class):
        """Test transaction pool is created per wallet."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        manager = XRPLWorkerPoolManager(
            node_pool=mock_node_pool,
            transaction_pool_size=2,
        )

        mock_wallet = MagicMock()
        mock_wallet.classic_address = "rTestAddress123456789"

        manager.get_transaction_pool(mock_wallet)

        mock_pool_class.assert_called_once()
        call_kwargs = mock_pool_class.call_args[1]
        self.assertEqual(call_kwargs['node_pool'], mock_node_pool)
        self.assertEqual(call_kwargs['wallet'], mock_wallet)
        self.assertEqual(call_kwargs['num_workers'], 2)
        self.assertIsNotNone(call_kwargs['pipeline'])

    @patch('hummingbot.connector.exchange.xrpl.xrpl_worker_manager.XRPLTransactionWorkerPool')
    def test_get_transaction_pool_reuses_for_same_wallet(self, mock_pool_class):
        """Test transaction pool is reused for the same wallet address."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        mock_wallet = MagicMock()
        mock_wallet.classic_address = "rTestAddress123456789"

        pool1 = manager.get_transaction_pool(mock_wallet)
        pool2 = manager.get_transaction_pool(mock_wallet)

        self.assertIs(pool1, pool2)
        mock_pool_class.assert_called_once()

    @patch('hummingbot.connector.exchange.xrpl.xrpl_worker_manager.XRPLTransactionWorkerPool')
    def test_get_transaction_pool_custom_pool_id(self, mock_pool_class):
        """Test transaction pool with custom pool_id."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        mock_pool = MagicMock()
        mock_pool_class.return_value = mock_pool

        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        mock_wallet = MagicMock()
        mock_wallet.classic_address = "rTestAddress123456789"

        manager.get_transaction_pool(mock_wallet, pool_id="custom_id")

        self.assertIn("custom_id", manager._transaction_pools)


class TestXRPLWorkerPoolManagerLifecycle(unittest.IsolatedAsyncioTestCase):
    """Async tests for lifecycle management."""

    async def test_start_sets_running(self):
        """Test start sets running flag."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        # Mock the pipeline by setting the internal attribute
        mock_pipeline = MagicMock()
        mock_pipeline.start = AsyncMock()
        manager._pipeline = mock_pipeline

        await manager.start()

        self.assertTrue(manager._running)
        mock_pipeline.start.assert_called_once()

    async def test_start_already_running(self):
        """Test start when already running does nothing."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)
        manager._running = True

        # Should not raise and should not start pipeline
        await manager.start()

    async def test_stop_sets_not_running(self):
        """Test stop clears running flag."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)
        manager._running = True

        # Create a mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.stop = AsyncMock()
        manager._pipeline = mock_pipeline

        await manager.stop()

        self.assertFalse(manager._running)
        mock_pipeline.stop.assert_called_once()

    async def test_stop_not_running(self):
        """Test stop when not running does nothing."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)
        manager._running = False

        # Should not raise
        await manager.stop()

    async def test_start_starts_existing_pools(self):
        """Test start starts any existing pools."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        # Mock the pipeline by setting the internal attribute
        mock_pipeline = MagicMock()
        mock_pipeline.start = AsyncMock()
        manager._pipeline = mock_pipeline

        # Create mock pools
        mock_query_pool = MagicMock()
        mock_query_pool.start = AsyncMock()
        manager._query_pool = mock_query_pool

        mock_verification_pool = MagicMock()
        mock_verification_pool.start = AsyncMock()
        manager._verification_pool = mock_verification_pool

        mock_tx_pool = MagicMock()
        mock_tx_pool.start = AsyncMock()
        manager._transaction_pools["wallet1"] = mock_tx_pool

        await manager.start()

        mock_query_pool.start.assert_called_once()
        mock_verification_pool.start.assert_called_once()
        mock_tx_pool.start.assert_called_once()

    async def test_stop_stops_all_pools(self):
        """Test stop stops all pools."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)
        manager._running = True

        # Create mock pools
        mock_query_pool = MagicMock()
        mock_query_pool.stop = AsyncMock()
        manager._query_pool = mock_query_pool

        mock_verification_pool = MagicMock()
        mock_verification_pool.stop = AsyncMock()
        manager._verification_pool = mock_verification_pool

        mock_tx_pool = MagicMock()
        mock_tx_pool.stop = AsyncMock()
        manager._transaction_pools["wallet1"] = mock_tx_pool

        mock_pipeline = MagicMock()
        mock_pipeline.stop = AsyncMock()
        manager._pipeline = mock_pipeline

        await manager.stop()

        mock_query_pool.stop.assert_called_once()
        mock_verification_pool.stop.assert_called_once()
        mock_tx_pool.stop.assert_called_once()
        mock_pipeline.stop.assert_called_once()


class TestXRPLWorkerPoolManagerStats(unittest.TestCase):
    """Tests for statistics and monitoring."""

    def test_get_stats_when_no_pools(self):
        """Test get_stats when no pools are initialized."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)

        stats = manager.get_stats()

        self.assertFalse(stats["running"])
        self.assertIsNone(stats["pipeline"])
        self.assertEqual(stats["pools"], {})

    def test_get_stats_with_pools(self):
        """Test get_stats includes pool stats."""
        mock_node_pool = MagicMock(spec=XRPLNodePool)
        manager = XRPLWorkerPoolManager(node_pool=mock_node_pool)
        manager._running = True

        # Mock query pool
        mock_query_stats = MagicMock()
        mock_query_stats.to_dict.return_value = {"total_requests": 100}
        mock_query_pool = MagicMock()
        mock_query_pool.stats = mock_query_stats
        manager._query_pool = mock_query_pool

        # Mock verification pool
        mock_verify_stats = MagicMock()
        mock_verify_stats.to_dict.return_value = {"total_requests": 50}
        mock_verify_pool = MagicMock()
        mock_verify_pool.stats = mock_verify_stats
        manager._verification_pool = mock_verify_pool

        # Mock transaction pool
        mock_tx_stats = MagicMock()
        mock_tx_stats.to_dict.return_value = {"total_requests": 25}
        mock_tx_pool = MagicMock()
        mock_tx_pool.stats = mock_tx_stats
        manager._transaction_pools["rTestAddress12345678"] = mock_tx_pool

        stats = manager.get_stats()

        self.assertTrue(stats["running"])
        self.assertEqual(stats["pools"]["query"], {"total_requests": 100})
        self.assertEqual(stats["pools"]["verification"], {"total_requests": 50})
        self.assertIn("tx_rTestAdd", stats["pools"])


if __name__ == "__main__":
    unittest.main()
