"""Test for GatewayStatusMonitor class."""
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from hummingbot.connector.gateway.core import GatewayStatus
from hummingbot.connector.gateway.core.gateway_monitor import GatewayStatusMonitor


class TestGatewayStatusMonitor(unittest.IsolatedAsyncioTestCase):
    """Test Gateway Monitor functionality."""

    def setUp(self):
        self.mock_client_config = Mock()
        self.mock_client_config.gateway = Mock()
        self.mock_client_config.gateway.gateway_api_host = "localhost"
        self.mock_client_config.gateway.gateway_api_port = 15888
        self.mock_client_config.gateway.gateway_use_ssl = False

    @patch('hummingbot.connector.gateway.core.gateway_monitor.GatewayHttpClient')
    async def test_monitor_initialization(self, mock_gateway_client_class):
        """Test monitor initialization."""
        mock_client = AsyncMock()
        mock_gateway_client_class.get_instance.return_value = mock_client

        monitor = GatewayStatusMonitor(self.mock_client_config)
        self.assertIsNotNone(monitor.client)
        self.assertEqual(monitor.gateway_status, GatewayStatus.OFFLINE)
        self.assertEqual(monitor.check_interval, 2.0)  # Default is 2.0, not 10.0

    @patch('hummingbot.connector.gateway.core.gateway_monitor.GatewayHttpClient')
    async def test_gateway_status_online(self, mock_gateway_client_class):
        """Test gateway status check when online."""
        mock_client = AsyncMock()
        mock_client.ping_gateway = AsyncMock(return_value=True)
        mock_client.initialize_gateway = AsyncMock()
        mock_gateway_client_class.get_instance.return_value = mock_client

        monitor = GatewayStatusMonitor(self.mock_client_config)

        # Test status check
        is_online = await monitor.check_once()
        self.assertTrue(is_online)

        # Start monitor to trigger status change
        await monitor.start()
        await asyncio.sleep(0.1)  # Let monitor update status
        await monitor.stop()

        self.assertEqual(monitor.gateway_status, GatewayStatus.ONLINE)
        mock_client.initialize_gateway.assert_called_once()

    @patch('hummingbot.connector.gateway.core.gateway_monitor.GatewayHttpClient')
    async def test_gateway_status_offline(self, mock_gateway_client_class):
        """Test gateway status check when offline."""
        mock_client = AsyncMock()
        mock_client.ping_gateway = AsyncMock(return_value=False)
        mock_gateway_client_class.get_instance.return_value = mock_client

        monitor = GatewayStatusMonitor(self.mock_client_config)

        # Test status check
        is_online = await monitor.check_once()
        self.assertFalse(is_online)

        # Monitor should remain offline
        self.assertEqual(monitor.gateway_status, GatewayStatus.OFFLINE)

    @patch('hummingbot.connector.gateway.core.gateway_monitor.GatewayHttpClient')
    async def test_start_stop_monitoring(self, mock_gateway_client_class):
        """Test starting and stopping the monitor."""
        mock_client = AsyncMock()
        mock_client.ping_gateway = AsyncMock(return_value=True)
        mock_client.initialize_gateway = AsyncMock()
        mock_gateway_client_class.get_instance.return_value = mock_client

        monitor = GatewayStatusMonitor(self.mock_client_config)
        monitor.check_interval = 0.1  # Fast interval for testing

        # Start monitoring
        await monitor.start()
        self.assertIsNotNone(monitor._monitor_task)
        self.assertFalse(monitor._monitor_task.done())

        # Let it run a bit
        await asyncio.sleep(0.2)

        # Stop monitoring
        await monitor.stop()
        self.assertTrue(monitor._monitor_task.done())

    @patch('hummingbot.connector.gateway.core.gateway_monitor.GatewayHttpClient')
    async def test_status_transition_offline_to_online(self, mock_gateway_client_class):
        """Test transition from offline to online status."""
        mock_client = AsyncMock()
        mock_client.ping_gateway = AsyncMock(return_value=False)
        mock_client.initialize_gateway = AsyncMock()
        mock_gateway_client_class.get_instance.return_value = mock_client

        monitor = GatewayStatusMonitor(self.mock_client_config)

        # Initially offline
        is_offline = await monitor.check_once()
        self.assertFalse(is_offline)

        # Track status changes
        status_changed = False

        async def on_available():
            nonlocal status_changed
            status_changed = True

        monitor.set_callbacks(on_available=on_available)

        # Now simulate coming online
        mock_client.ping_gateway.return_value = True

        # Start monitor to detect change
        await monitor.start()
        await asyncio.sleep(0.15)  # Let monitor detect change
        await monitor.stop()

        self.assertTrue(status_changed)
        self.assertEqual(monitor.gateway_status, GatewayStatus.ONLINE)

        # Verify initialization was called on transition
        mock_client.initialize_gateway.assert_called_once()

    @patch('hummingbot.connector.gateway.core.gateway_monitor.GatewayHttpClient')
    async def test_initialization_error_handling(self, mock_gateway_client_class):
        """Test error handling during gateway initialization."""
        mock_client = AsyncMock()
        mock_client.ping_gateway = AsyncMock(return_value=True)
        mock_client.initialize_gateway = AsyncMock(side_effect=Exception("Init failed"))
        mock_gateway_client_class.get_instance.return_value = mock_client

        monitor = GatewayStatusMonitor(self.mock_client_config)

        # Start monitor to trigger initialization
        await monitor.start()
        await asyncio.sleep(0.1)  # Let monitor run
        await monitor.stop()

        # Should handle initialization error gracefully
        self.assertEqual(monitor.gateway_status, GatewayStatus.ONLINE)
        mock_client.initialize_gateway.assert_called_once()

    @patch('hummingbot.connector.gateway.core.gateway_monitor.GatewayHttpClient')
    async def test_continuous_monitoring(self, mock_gateway_client_class):
        """Test continuous monitoring with status changes."""
        mock_client = AsyncMock()
        mock_client.initialize_gateway = AsyncMock()

        # Track calls to ping_gateway
        ping_call_count = 0

        def ping_side_effect():
            nonlocal ping_call_count
            ping_call_count += 1
            # First few calls return True, then False, then True again
            if ping_call_count <= 2:
                return True
            elif ping_call_count <= 4:
                return False
            else:
                return True

        mock_client.ping_gateway = AsyncMock(side_effect=ping_side_effect)

        mock_gateway_client_class.get_instance.return_value = mock_client

        monitor = GatewayStatusMonitor(self.mock_client_config)
        monitor.check_interval = 0.05  # Very fast for testing

        # Track status changes
        status_changes = []

        # Create callbacks to track status changes
        async def on_available():
            status_changes.append(GatewayStatus.ONLINE)

        async def on_unavailable():
            status_changes.append(GatewayStatus.OFFLINE)

        monitor.set_callbacks(on_available, on_unavailable)

        # Start monitoring
        await monitor.start()

        # Wait for enough status checks
        await asyncio.sleep(0.35)

        # Stop monitoring
        await monitor.stop()

        # Verify we got status transitions
        self.assertGreater(len(status_changes), 0)  # At least some status changes
        self.assertEqual(status_changes[0], GatewayStatus.ONLINE)  # First becomes online

        # Verify ping was called multiple times
        self.assertGreater(ping_call_count, 4)


if __name__ == "__main__":
    unittest.main()
