#!/usr/bin/env python3

import unittest
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.coinsxyz.coinsxyz_websocket_connection_manager import (
    CoinsxyzWebSocketConnectionManager,
)


class TestCoinsxyzWebSocketConnectionManager(unittest.TestCase):
    """Unit tests for CoinsxyzWebSocketConnectionManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.connection_manager = CoinsxyzWebSocketConnectionManager()

    def test_init(self):
        """Test connection manager initialization."""
        self.assertIsNotNone(self.connection_manager)

    @patch('websockets.connect')
    async def test_connect_websocket(self, mock_connect):
        """Test WebSocket connection establishment."""
        mock_websocket = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_websocket

        result = await self.connection_manager.connect("wss://test.url")

        self.assertIsNotNone(result)
        mock_connect.assert_called_once()

    def test_is_connected(self):
        """Test connection status check."""
        # Initially not connected
        self.assertFalse(self.connection_manager.is_connected())

    async def test_disconnect(self):
        """Test WebSocket disconnection."""
        # Should handle disconnect gracefully even when not connected
        await self.connection_manager.disconnect()
        self.assertFalse(self.connection_manager.is_connected())

    def test_get_connection_url(self):
        """Test connection URL generation."""
        url = self.connection_manager.get_connection_url()
        self.assertIsInstance(url, str)
        self.assertTrue(url.startswith("wss://"))


if __name__ == "__main__":
    unittest.main()
