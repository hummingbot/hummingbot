import unittest
from unittest.mock import MagicMock

from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_auth import BackpackPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TestBackpackPerpetualAuth(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"
        self.auth = BackpackPerpetualAuth(api_key=self.api_key, api_secret=self.api_secret)

    def test_api_key_property(self):
        self.assertEqual(self.auth.api_key, self.api_key)

    def test_api_secret_property(self):
        self.assertEqual(self.auth.api_secret, self.api_secret)


if __name__ == "__main__":
    unittest.main()
