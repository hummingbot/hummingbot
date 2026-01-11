import unittest
from unittest.mock import MagicMock

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TestEvedexPerpetualAuth(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"
        self.auth = EvedexPerpetualAuth(api_key=self.api_key, api_secret=self.api_secret)

    def test_api_key_property(self):
        self.assertEqual(self.auth.api_key, self.api_key)

    def test_api_secret_property(self):
        self.assertEqual(self.auth.api_secret, self.api_secret)


if __name__ == "__main__":
    unittest.main()
