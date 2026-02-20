import unittest
from unittest.mock import patch

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import EXCHANGE_NAME


class TestDecibelPerpetualAuth(unittest.TestCase):
    """Unit tests for DecibelPerpetualAuth"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_token = "test_bearer_token_12345"
        self.test_origin = "https://app.decibel.trade"
        self.auth = DecibelPerpetualAuth(bearer_token=self.test_token, origin=self.test_origin)

    def test_init_with_default_origin(self):
        """Test initialization with default origin"""
        auth = DecibelPerpetualAuth(bearer_token="token123")
        self.assertEqual(auth._bearer_token, "token123")
        self.assertEqual(auth._origin, "https://app.decibel.trade")

    def test_init_with_custom_origin(self):
        """Test initialization with custom origin"""
        auth = DecibelPerpetualAuth(bearer_token="token123", origin="https://test.decibel.trade")
        self.assertEqual(auth._origin, "https://test.decibel.trade")

    def test_api_key_property(self):
        """Test api_key property returns bearer token"""
        self.assertEqual(self.auth.api_key, self.test_token)

    def test_auth_headers(self):
        """Test auth_headers property"""
        headers = self.auth.auth_headers
        self.assertEqual(headers["Authorization"], f"Bearer {self.test_token}")
        self.assertEqual(headers["Origin"], self.test_origin)

    def test_get_headers(self):
        """Test get_headers method"""
        headers = self.auth.get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Authorization"], f"Bearer {self.test_token}")
        self.assertEqual(headers["Origin"], self.test_origin)

    def test_get_account_id(self):
        """Test get_account_id method"""
        account_id = self.auth.get_account_id()
        self.assertEqual(account_id, "main")

    def test_get_subaccount_id(self):
        """Test get_subaccount_id method returns None by default"""
        subaccount_id = self.auth.get_subaccount_id()
        self.assertIsNone(subaccount_id)

    def test_headers_are_immutable_per_instance(self):
        """Test that headers are properly isolated per instance"""
        auth1 = DecibelPerpetualAuth(bearer_token="token1", origin="https://app1.decibel.trade")
        auth2 = DecibelPerpetualAuth(bearer_token="token2", origin="https://app2.decibel.trade")

        headers1 = auth1.get_headers()
        headers2 = auth2.get_headers()

        self.assertNotEqual(headers1["Authorization"], headers2["Authorization"])
        self.assertNotEqual(headers1["Origin"], headers2["Origin"])


if __name__ == "__main__":
    unittest.main()
