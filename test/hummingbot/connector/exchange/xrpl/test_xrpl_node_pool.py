"""
Unit tests for XRPLNodePool with persistent connections and health monitoring.
"""
import asyncio
import unittest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.asyncio.clients import AsyncWebsocketClient

from hummingbot.connector.exchange.xrpl.xrpl_utils import RateLimiter, XRPLConnection, XRPLConnectionError, XRPLNodePool


class TestRateLimiter(unittest.TestCase):
    """Tests for the RateLimiter class."""

    def test_init_defaults(self):
        """Test RateLimiter initializes with correct defaults."""
        limiter = RateLimiter(requests_per_10s=20)
        self.assertEqual(limiter._rate_limit, 20)
        self.assertEqual(limiter._burst_tokens, 0)
        self.assertEqual(limiter._max_burst_tokens, 5)

    def test_init_with_burst(self):
        """Test RateLimiter initializes with burst tokens."""
        limiter = RateLimiter(requests_per_10s=10, burst_tokens=3, max_burst_tokens=10)
        self.assertEqual(limiter._burst_tokens, 3)
        self.assertEqual(limiter._max_burst_tokens, 10)

    def test_add_burst_tokens(self):
        """Test adding burst tokens."""
        limiter = RateLimiter(requests_per_10s=10, burst_tokens=0, max_burst_tokens=5)
        limiter.add_burst_tokens(3)
        self.assertEqual(limiter._burst_tokens, 3)

    def test_add_burst_tokens_capped(self):
        """Test burst tokens are capped at max."""
        limiter = RateLimiter(requests_per_10s=10, burst_tokens=3, max_burst_tokens=5)
        limiter.add_burst_tokens(10)
        self.assertEqual(limiter._burst_tokens, 5)

    def test_burst_tokens_property(self):
        """Test burst_tokens property."""
        limiter = RateLimiter(requests_per_10s=10, burst_tokens=3, max_burst_tokens=5)
        self.assertEqual(limiter.burst_tokens, 3)


class TestXRPLConnection(unittest.TestCase):
    """Tests for XRPLConnection dataclass."""

    def test_init_defaults(self):
        """Test XRPLConnection initializes with correct defaults."""
        conn = XRPLConnection(url="wss://test.com")
        self.assertEqual(conn.url, "wss://test.com")
        self.assertIsNone(conn.client)
        self.assertTrue(conn.is_healthy)  # Default is True - connection is assumed healthy until proven otherwise
        self.assertEqual(conn.request_count, 0)
        self.assertEqual(conn.error_count, 0)
        self.assertEqual(conn.avg_latency, 0.0)

    def test_is_open_no_client(self):
        """Test is_open returns False when no client."""
        conn = XRPLConnection(url="wss://test.com")
        self.assertFalse(conn.is_open)

    def test_is_open_with_client(self):
        """Test is_open checks client.is_open()."""
        mock_client = MagicMock(spec=AsyncWebsocketClient)
        mock_client.is_open.return_value = True
        conn = XRPLConnection(url="wss://test.com", client=mock_client)
        self.assertTrue(conn.is_open)


class TestXRPLNodePoolInit(unittest.TestCase):
    """Tests for XRPLNodePool initialization."""

    def test_init_with_urls(self):
        """Test initialization with provided URLs."""
        urls = ["wss://node1.com", "wss://node2.com"]
        pool = XRPLNodePool(node_urls=urls)
        self.assertEqual(pool._node_urls, urls)
        self.assertFalse(pool._running)

    def test_init_default_urls(self):
        """Test initialization uses default URLs when empty."""
        pool = XRPLNodePool(node_urls=[])
        self.assertEqual(pool._node_urls, XRPLNodePool.DEFAULT_NODES)

    def test_init_rate_limiter(self):
        """Test rate limiter is initialized correctly."""
        pool = XRPLNodePool(
            node_urls=["wss://test.com"],
            requests_per_10s=30,
            burst_tokens=5,
            max_burst_tokens=10,
        )
        self.assertEqual(pool._rate_limiter._rate_limit, 30)
        self.assertEqual(pool._rate_limiter._burst_tokens, 5)


class TestXRPLNodePoolAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for XRPLNodePool."""

    async def test_start_stop(self):
        """Test start and stop lifecycle."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])

        # Mock connection initialization
        with patch.object(pool, '_init_connection', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = True
            await pool.start()

            self.assertTrue(pool._running)
            self.assertIsNotNone(pool._health_check_task)
            mock_init.assert_called_once_with("wss://test.com")

        await pool.stop()
        self.assertFalse(pool._running)
        self.assertIsNone(pool._health_check_task)

    async def test_start_already_running(self):
        """Test start when already running does nothing."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True

        with patch.object(pool, '_init_connection', new_callable=AsyncMock) as mock_init:
            await pool.start()
            mock_init.assert_not_called()

    async def test_stop_not_running(self):
        """Test stop when not running does nothing."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = False

        # Should not raise
        await pool.stop()

    async def test_healthy_connection_count(self):
        """Test healthy_connection_count property."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._healthy_connections = deque(["wss://test.com", "wss://test2.com"])

        self.assertEqual(pool.healthy_connection_count, 2)

    async def test_total_connection_count(self):
        """Test total_connection_count property."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._connections = {
            "wss://test.com": XRPLConnection(url="wss://test.com"),
            "wss://test2.com": XRPLConnection(url="wss://test2.com"),
        }

        self.assertEqual(pool.total_connection_count, 2)

    async def test_get_client_not_running(self):
        """Test get_client raises XRPLConnectionError when no healthy connections available."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = False

        with self.assertRaises(XRPLConnectionError):
            await pool.get_client()

    async def test_mark_bad_node(self):
        """Test marking a node as bad."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True

        # Create a connection
        conn = XRPLConnection(url="wss://test.com", is_healthy=True)
        pool._connections["wss://test.com"] = conn
        pool._healthy_connections.append("wss://test.com")

        # Mark as bad
        pool.mark_bad_node("wss://test.com")

        self.assertFalse(conn.is_healthy)
        self.assertIn("wss://test.com", pool._bad_nodes)

    async def test_add_burst_tokens(self):
        """Test adding burst tokens to rate limiter."""
        pool = XRPLNodePool(
            node_urls=["wss://test.com"],
            burst_tokens=0,
            max_burst_tokens=10,
        )

        pool.add_burst_tokens(5)
        self.assertEqual(pool._rate_limiter.burst_tokens, 5)


class TestXRPLNodePoolHealthMonitor(unittest.IsolatedAsyncioTestCase):
    """Tests for health monitoring functionality."""

    async def test_health_monitor_cancellation(self):
        """Test health monitor handles cancellation gracefully."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._running = True
        pool._health_check_interval = 0.1  # Short interval for testing

        # Mock _check_all_connections to track calls
        check_called = asyncio.Event()

        async def mock_check():
            check_called.set()

        with patch.object(pool, '_check_all_connections', side_effect=mock_check):
            task = asyncio.create_task(pool._health_monitor_loop())

            # Wait for at least one check
            try:
                await asyncio.wait_for(check_called.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

            # Cancel the task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def test_check_all_connections_empty(self):
        """Test _check_all_connections with no connections."""
        pool = XRPLNodePool(node_urls=["wss://test.com"])
        pool._connections = {}

        # Should not raise
        await pool._check_all_connections()


if __name__ == "__main__":
    unittest.main()
