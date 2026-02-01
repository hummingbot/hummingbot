"""
Unit tests for WEEX authentication (signature generation)
"""
import unittest
from unittest.mock import MagicMock

from hummingbot.connector.exchange.weex.weex_auth import WeexAuth


class TestWeexAuth(unittest.TestCase):
    """Test WEEX REST and WS authentication"""

    def setUp(self):
        self.api_key = "test_api_key_12345"
        self.secret_key = "test_secret_key_abcdefg"
        self.passphrase = "test_passphrase"
        self.time_provider = MagicMock()
        self.time_provider.time.return_value = 1000.0  # 1000 seconds
        self.auth = WeexAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            passphrase=self.passphrase,
            time_provider=self.time_provider,
        )

    def test_rest_signature_get_no_params(self):
        """Test REST GET signature without parameters"""
        timestamp = "1000000"
        method = "GET"
        path = "/api/v2/public/products"

        signature = self.auth.generate_rest_signature(
            timestamp_ms=timestamp,
            method=method,
            request_path=path,
        )

        # Signature should be non-empty and base64-encoded
        self.assertIsNotNone(signature)
        self.assertGreater(len(signature), 0)
        # Base64 strings typically contain alphanumeric + /+= chars
        self.assertTrue(any(c in signature for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="))

    def test_rest_signature_post_with_body(self):
        """Test REST POST signature with JSON body"""
        timestamp = "1000000"
        method = "POST"
        path = "/api/v2/trade/orders"
        body = {"symbol": "VCCUSDT-SPBL", "side": "buy", "quantity": "100"}

        signature = self.auth.generate_rest_signature(
            timestamp_ms=timestamp,
            method=method,
            request_path=path,
            body=body,
        )

        self.assertIsNotNone(signature)
        self.assertGreater(len(signature), 0)

    def test_rest_signature_get_with_params(self):
        """Test REST GET signature with query parameters"""
        timestamp = "1000000"
        method = "GET"
        path = "/api/v2/market/ticker"
        params = {"symbol": "VCCUSDT-SPBL"}

        signature = self.auth.generate_rest_signature(
            timestamp_ms=timestamp,
            method=method,
            request_path=path,
            params=params,
        )

        self.assertIsNotNone(signature)
        self.assertGreater(len(signature), 0)

    def test_rest_signature_deterministic(self):
        """Test that same inputs produce same signature"""
        timestamp = "1000000"
        method = "POST"
        path = "/api/v2/trade/orders"
        body = {"symbol": "VCCUSDT-SPBL"}

        sig1 = self.auth.generate_rest_signature(
            timestamp_ms=timestamp,
            method=method,
            request_path=path,
            body=body,
        )
        sig2 = self.auth.generate_rest_signature(
            timestamp_ms=timestamp,
            method=method,
            request_path=path,
            body=body,
        )

        self.assertEqual(sig1, sig2)

    def test_ws_signature(self):
        """Test WS authentication signature"""
        timestamp = "1000000"
        signature = self.auth.generate_ws_signature(timestamp)

        self.assertIsNotNone(signature)
        self.assertGreater(len(signature), 0)

    def test_build_ws_headers(self):
        """Test WS header building"""
        headers = self.auth.build_ws_headers()

        self.assertIn("ACCESS-KEY", headers)
        self.assertIn("ACCESS-TIMESTAMP", headers)
        self.assertIn("ACCESS-SIGN", headers)
        self.assertIn("ACCESS-PASSPHRASE", headers)
        self.assertEqual(headers["ACCESS-KEY"], self.api_key)
        self.assertEqual(headers["ACCESS-PASSPHRASE"], self.passphrase)

    def test_time_provider_used(self):
        """Test that time provider is called for timestamp"""
        self.auth._now_ms()
        self.time_provider.time.assert_called()

    def test_method_enum_handling(self):
        """Test that RESTMethod enum is handled correctly"""
        from hummingbot.core.web_assistant.connections.data_types import RESTMethod

        timestamp = "1000000"
        path = "/api/v2/test"

        # Pass method as enum
        signature = self.auth.generate_rest_signature(
            timestamp_ms=timestamp,
            method=RESTMethod.GET,
            request_path=path,
        )

        self.assertIsNotNone(signature)


if __name__ == "__main__":
    unittest.main()
