"""Tests for Backpack authentication."""
import unittest
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth


class TestBackpackAuth(unittest.TestCase):
    """Test cases for BackpackAuth."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key"
        self.secret_key = "dGVzdF9zZWNyZXRfa2V5"  # base64 encoded "test_secret_key"
        self.auth = BackpackAuth(api_key=self.api_key, secret_key=self.secret_key)

    def test_header_for_authentication(self):
        """Test that authentication headers are correctly generated."""
        headers = self.auth.header_for_authentication()
        
        self.assertIn("X-API-Key", headers)
        self.assertEqual(headers["X-API-Key"], self.api_key)
        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_add_auth_to_params_adds_timestamp(self):
        """Test that authentication adds timestamp to params."""
        params = {"symbol": "SOL_USDC"}
        url = "https://api.backpack.exchange/api/v1/order"
        
        result = self.auth.add_auth_to_params(params, url, "POST")
        
        self.assertIn("timestamp", result)
        self.assertIn("signature", result)
        self.assertEqual(result["symbol"], "SOL_USDC")

    def test_add_auth_to_params_preserves_existing_params(self):
        """Test that existing params are preserved."""
        params = {"symbol": "SOL_USDC", "side": "Bid", "quantity": "1.0"}
        url = "https://api.backpack.exchange/api/v1/order"
        
        result = self.auth.add_auth_to_params(params, url, "POST")
        
        self.assertEqual(result["symbol"], "SOL_USDC")
        self.assertEqual(result["side"], "Bid")
        self.assertEqual(result["quantity"], "1.0")
        self.assertIn("timestamp", result)
        self.assertIn("signature", result)

    @patch("time.time")
    def test_get_timestamp(self, mock_time):
        """Test timestamp generation."""
        mock_time.return_value = 1234567890.123
        
        timestamp = self.auth._get_timestamp()
        
        self.assertEqual(timestamp, 1234567890123)  # Converted to milliseconds

    def test_generate_websocket_auth_message(self):
        """Test WebSocket authentication message generation."""
        auth_message = self.auth.generate_websocket_auth_message()
        
        self.assertIn("method", auth_message)
        self.assertEqual(auth_message["method"], "subscribe")
        self.assertIn("signature", auth_message)
        self.assertIn("apiKey", auth_message)
        self.assertEqual(auth_message["apiKey"], self.api_key)
        self.assertIn("timestamp", auth_message)


if __name__ == "__main__":
    unittest.main()
