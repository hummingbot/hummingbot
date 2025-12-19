#!/usr/bin/env python3
"""
Unit Tests for Coins.xyz API Client
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinsxyz.coinsxyz_api_client import CoinsxyzAPIClient
from hummingbot.connector.exchange.coinsxyz.coinsxyz_exceptions import CoinsxyzAPIError


class TestCoinsxyzAPIClient(unittest.TestCase):
    """Unit tests for CoinsxyzAPIClient."""

    def setUp(self):
        """Set up test fixtures."""
        self.auth = MagicMock()
        self.client = CoinsxyzAPIClient(auth=self.auth)

    def test_init(self):
        """Test API client initialization."""
        self.assertIsNotNone(self.client._auth)
        self.assertEqual(self.client._auth, self.auth)

    @patch('aiohttp.ClientSession.request')
    async def test_get_request(self, mock_request):
        """Test GET request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value.__aenter__.return_value = mock_response

        result = await self.client._get("/test/endpoint")

        self.assertEqual(result["status"], "success")
        mock_request.assert_called_once()

    @patch('aiohttp.ClientSession.request')
    async def test_post_request(self, mock_request):
        """Test POST request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"orderId": "12345"}
        mock_request.return_value.__aenter__.return_value = mock_response

        result = await self.client._post("/test/endpoint", {"symbol": "BTCUSDT"})

        self.assertEqual(result["orderId"], "12345")

    @patch('aiohttp.ClientSession.request')
    async def test_delete_request(self, mock_request):
        """Test DELETE request."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {"status": "CANCELED"}
        mock_request.return_value.__aenter__.return_value = mock_response

        result = await self.client._delete("/test/endpoint")

        self.assertEqual(result["status"], "CANCELED")

    @patch('aiohttp.ClientSession.request')
    async def test_api_error_handling(self, mock_request):
        """Test API error handling."""
        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.json.return_value = {"code": -1121, "msg": "Invalid symbol"}
        mock_request.return_value.__aenter__.return_value = mock_response

        with self.assertRaises(CoinsxyzAPIError):
            await self.client._get("/test/endpoint")

    async def test_get_server_time(self):
        """Test server time retrieval."""
        with patch.object(self.client, '_get') as mock_get:
            mock_get.return_value = {"serverTime": 1234567890000}

            server_time = await self.client.get_server_time()

            self.assertEqual(server_time, 1234567890000)

    async def test_get_exchange_info(self):
        """Test exchange info retrieval."""
        with patch.object(self.client, '_get') as mock_get:
            mock_get.return_value = {
                "symbols": [
                    {"symbol": "BTCUSDT", "status": "TRADING"}
                ]
            }

            exchange_info = await self.client.get_exchange_info()

            self.assertIn("symbols", exchange_info)

    async def test_get_account_info(self):
        """Test account info retrieval."""
        with patch.object(self.client, '_get') as mock_get:
            mock_get.return_value = {
                "balances": [
                    {"asset": "BTC", "free": "1.0", "locked": "0.5"}
                ]
            }

            account_info = await self.client.get_account_info()

            self.assertIn("balances", account_info)


if __name__ == "__main__":
    unittest.main()
