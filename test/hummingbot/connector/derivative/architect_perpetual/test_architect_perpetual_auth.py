import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', '..'))

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth


class TestArchitectPerpetualAuth(unittest.TestCase):

    def setUp(self):
        self.api_key = "test_api_key_12345"
        self.api_secret = "test_api_secret_67890"
        self.auth = ArchitectPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            paper_trading=False
        )

    def test_init(self):
        self.assertEqual(self.auth._api_key, self.api_key)
        self.assertEqual(self.auth._api_secret, self.api_secret)
        self.assertFalse(self.auth._paper_trading)
        self.assertIsNone(self.auth._architect_client)

    def test_api_key_property(self):
        self.assertEqual(self.auth.api_key, self.api_key)

    def test_api_secret_property(self):
        self.assertEqual(self.auth.api_secret, self.api_secret)

    def test_paper_trading_property(self):
        self.assertFalse(self.auth.paper_trading)

    def test_paper_trading_enabled(self):
        auth_paper = ArchitectPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            paper_trading=True
        )
        self.assertTrue(auth_paper.paper_trading)


class TestArchitectPerpetualAuthAsync(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.api_key = "test_api_key_12345"
        self.api_secret = "test_api_secret_67890"
        self.auth = ArchitectPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            paper_trading=True
        )

    async def test_rest_authenticate_passthrough(self):
        mock_request = MagicMock()
        result = await self.auth.rest_authenticate(mock_request)
        self.assertEqual(result, mock_request)

    async def test_ws_authenticate_passthrough(self):
        mock_request = MagicMock()
        result = await self.auth.ws_authenticate(mock_request)
        self.assertEqual(result, mock_request)

    async def test_close_client_when_none(self):
        await self.auth.close_client()
        self.assertIsNone(self.auth._architect_client)


if __name__ == "__main__":
    unittest.main()
