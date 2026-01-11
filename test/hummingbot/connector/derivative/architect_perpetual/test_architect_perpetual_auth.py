import unittest
from unittest.mock import MagicMock

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TestArchitectPerpetualAuth(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"
        self.auth = ArchitectPerpetualAuth(api_key=self.api_key, api_secret=self.api_secret)

    def test_api_key_property(self):
        self.assertEqual(self.auth.api_key, self.api_key)

    def test_api_secret_property(self):
        self.assertEqual(self.auth.api_secret, self.api_secret)

    def test_get_credentials(self):
        credentials = self.auth.get_credentials()
        self.assertIsInstance(credentials, dict)
        self.assertEqual(credentials["api_key"], self.api_key)
        self.assertEqual(credentials["api_secret"], self.api_secret)

    def test_set_jwt_token(self):
        token = "test_jwt_token"
        expiry = 1234567890.0
        self.auth.set_jwt_token(token, expiry)
        self.assertEqual(self.auth._jwt_token, token)
        self.assertEqual(self.auth._jwt_expiry, expiry)

    def test_is_token_valid_without_token(self):
        self.assertFalse(self.auth.is_token_valid())

    def test_clear_token(self):
        self.auth.set_jwt_token("token", 999999999999.0)
        self.auth.clear_token()
        self.assertIsNone(self.auth._jwt_token)
        self.assertIsNone(self.auth._jwt_expiry)


if __name__ == "__main__":
    unittest.main()
