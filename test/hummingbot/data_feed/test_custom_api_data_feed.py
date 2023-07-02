import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from hummingbot.core.network_base import NetworkBase, NetworkStatus
from hummingbot.data_feed.custom_api_data_feed import CustomAPIDataFeed


class CustomAPIDataFeedUnitTest(unittest.TestCase):
    ev_loop = None

    @classmethod
    def setUpClass(cls):
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

    def run_async(self, async_fn):
        return self.ev_loop.run_until_complete(async_fn)

    def test_check_network(self):
        async def async_test():
            api_url = "https://example.com/api"
            response_text = "Custom API Feed server is healthy"
            custom_api = CustomAPIDataFeed(api_url)

            async with aiohttp.ClientSession() as session:
                session.request = MagicMock()
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.text = AsyncMock()
                mock_response.text.return_value = response_text
                session.request.return_value.__aenter__.return_value = mock_response

                custom_api._http_client = MagicMock(return_value=session)

                result = await custom_api.check_network()

                self.assertEqual(result, NetworkStatus.CONNECTED)
        self.run_async(async_test())

    def test_get_price(self):
        custom_api = CustomAPIDataFeed("https://example.com/api")
        custom_api._price = Decimal("123.45")

        result = custom_api.get_price()

        self.assertEqual(result, Decimal("123.45"))

    def test_fetch_price_loop(self):
        async def async_test():
            api_url = "https://example.com/api"
            response_text = "123.45"
            custom_api = CustomAPIDataFeed(api_url, update_interval=0.1)

            async with aiohttp.ClientSession() as session:
                session.request = MagicMock()
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.text = AsyncMock()
                mock_response.text.return_value = response_text
                session.request.return_value.__aenter__.return_value = mock_response

                custom_api._http_client = MagicMock(return_value=session)

                fetch_price_task = asyncio.ensure_future(custom_api.fetch_price_loop())

                await asyncio.sleep(0.5)

                await custom_api.stop_network()
                fetch_price_task.cancel()

                self.assertEqual(custom_api.get_price(), Decimal(response_text))
                session.request.assert_called()
                mock_response.text.assert_awaited()
        self.run_async(async_test())

    def test_fetch_price(self):
        async def async_test():
            api_url = "https://example.com/api"
            response_text = "123.45"
            custom_api = CustomAPIDataFeed(api_url)

            async with aiohttp.ClientSession() as session:
                session.request = MagicMock()
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.text = AsyncMock()
                mock_response.text.return_value = response_text
                session.request.return_value.__aenter__.return_value = mock_response

                custom_api._http_client = MagicMock(return_value=session)

                await custom_api.fetch_price()

                self.assertEqual(custom_api.get_price(), Decimal(response_text))
                session.request.assert_called_once_with("GET", api_url)
                mock_response.text.assert_awaited_once()
        self.run_async(async_test())

    def test_start_network(self):
        async def async_test():
            api_url = "https://example.com/api"
            response_text = "123.45"
            custom_api = CustomAPIDataFeed(api_url, update_interval=0.1)

            async with aiohttp.ClientSession() as session:
                session.request = MagicMock()
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.text = AsyncMock()
                mock_response.text.return_value = response_text
                session.request.return_value.__aenter__.return_value = mock_response

                custom_api._http_client = MagicMock(return_value=session)

                await custom_api.start_network()
                await asyncio.sleep(0.5)
                await custom_api.stop_network()

                self.assertEqual(custom_api.get_price(), Decimal(response_text))
                session.request.assert_called()
                mock_response.text.assert_awaited()
        self.run_async(async_test())

    def test_stop_network(self):
        api_url = "https://example.com/api"
        custom_api = CustomAPIDataFeed(api_url)

        custom_api._fetch_price_task = MagicMock()

        self.run_async(custom_api.stop_network())

        self.assertIsNone(custom_api._fetch_price_task)

    @patch.object(NetworkBase, "start")
    def test_start(self, start_network):
        custom_api = CustomAPIDataFeed("https://example.com/api")

        custom_api.start()

        start_network.assert_called_once()

    @patch.object(NetworkBase, "stop")
    def test_stop(self, stop_network):
        custom_api = CustomAPIDataFeed("https://example.com/api")

        custom_api.stop()

        stop_network.assert_called_once()
