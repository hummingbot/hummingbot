import asyncio
import unittest
from unittest.mock import MagicMock, patch

from aioresponses import aioresponses
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.data_feed_base import DataFeedBase


class TestDataFeedBase(unittest.TestCase):

    class TestDataFeed(DataFeedBase):
        @property
        def name(self):
            return "Test Data Feed"

        @property
        def price_dict(self):
            return {"ETH": 1000.0, "BTC": 50000.0}

        @property
        def health_check_endpoint(self):
            return "https://api.example.com/health"

        def get_price(self, asset: str):
            return self.price_dict.get(asset, 0.0)

    def setUp(self):
        self.data_feed = self.TestDataFeed()

    def test_name(self):
        self.assertEqual(self.data_feed.name, "Test Data Feed")

    def test_price_dict(self):
        self.assertEqual(self.data_feed.price_dict, {"ETH": 1000.0, "BTC": 50000.0})

    def test_health_check_endpoint(self):
        self.assertEqual(self.data_feed.health_check_endpoint, "https://api.example.com/health")

    def test_get_price(self):
        self.assertEqual(self.data_feed.get_price("ETH"), 1000.0)
        self.assertEqual(self.data_feed.get_price("BTC"), 50000.0)
        self.assertEqual(self.data_feed.get_price("USDT"), 0.0)

    @aioresponses()
    def test_check_network_connected(self, mock_api):
        mock_api.get("https://api.example.com/health", status=200, body=str(NetworkStatus.CONNECTED))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.data_feed.check_network())
        self.assertEqual(result, NetworkStatus.CONNECTED)

    @patch("aiohttp.ClientSession")
    def test_check_network_not_connected(self, mock_client_session):
        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_client_session.return_value.get.return_value.__aenter__.return_value = mock_resp

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.data_feed.check_network())
        self.assertEqual(result, NetworkStatus.NOT_CONNECTED)
