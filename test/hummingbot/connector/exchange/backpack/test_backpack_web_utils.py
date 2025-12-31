import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase, async_to_sync
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack import backpack_web_utils as web_utils
from hummingbot.connector.exchange.backpack.backpack_web_utils import BackpackRESTPreProcessor
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TestBackpackWebUtils(unittest.TestCase):
    """Test suite for Backpack web utilities."""

    def test_rest_url_mainnet(self):
        """Test REST URL generation for mainnet."""
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL, CONSTANTS.DOMAIN)

        self.assertEqual(f"{CONSTANTS.BASE_URL}{CONSTANTS.MARKETS_URL}", url)

    def test_rest_url_testnet(self):
        """Test REST URL generation for testnet."""
        url = web_utils.rest_url(CONSTANTS.MARKETS_URL, CONSTANTS.TESTNET_DOMAIN)

        self.assertEqual(f"{CONSTANTS.TESTNET_BASE_URL}{CONSTANTS.MARKETS_URL}", url)

    def test_wss_url_mainnet(self):
        """Test WebSocket URL generation for mainnet."""
        url = web_utils.wss_url(CONSTANTS.DOMAIN)

        self.assertEqual(CONSTANTS.WS_URL, url)

    def test_wss_url_testnet(self):
        """Test WebSocket URL generation for testnet."""
        url = web_utils.wss_url(CONSTANTS.TESTNET_DOMAIN)

        self.assertEqual(CONSTANTS.TESTNET_WS_URL, url)

    def test_build_api_factory(self):
        """Test API factory creation."""
        factory = web_utils.build_api_factory(throttler=None, auth=None)

        self.assertIsNotNone(factory)
        self.assertTrue(hasattr(factory, "get_rest_assistant"))

    def test_build_api_factory_without_time_sync(self):
        from hummingbot.core.api_throttler.async_throttler import AsyncThrottler

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
        self.assertIsNotNone(factory)

    def test_rest_url_with_various_endpoints(self):
        """Test REST URL generation for various endpoints."""
        endpoints = [
            CONSTANTS.MARKETS_URL,
            CONSTANTS.ORDER_URL,
            CONSTANTS.CAPITAL_URL,
            CONSTANTS.TICKER_URL,
            CONSTANTS.DEPTH_URL,
        ]

        for endpoint in endpoints:
            url = web_utils.rest_url(endpoint, CONSTANTS.DOMAIN)
            self.assertTrue(url.startswith(CONSTANTS.BASE_URL))
            self.assertTrue(url.endswith(endpoint))

    def test_rest_pre_processor_sets_content_type(self):
        request = RESTRequest(method=RESTMethod.GET, url="https://example.com")
        processor = BackpackRESTPreProcessor()
        processed = async_to_sync(processor.pre_process)(request)
        self.assertEqual("application/json", processed.headers["Content-Type"])

    def test_symbol_helpers(self):
        self.assertTrue(web_utils.is_exchange_information_valid({"any": "thing"}))
        self.assertEqual("BTC_USDC", web_utils.convert_to_exchange_symbol("BTC-USDC"))
        self.assertEqual("BTC-USDC", web_utils.convert_from_exchange_symbol("BTC_USDC"))
        self.assertEqual(("BTC", "USDC"), web_utils.get_base_quote_from_symbol("BTC_USDC"))
        with self.assertRaises(ValueError):
            web_utils.get_base_quote_from_symbol("INVALID")


class TestBackpackWebUtilsAsync(IsolatedAsyncioWrapperTestCase):
    async def test_get_current_server_time_from_seconds(self):
        rest_assistant = AsyncMock()
        rest_assistant.execute_request = AsyncMock(return_value={"serverTime": "1700000000"})
        api_factory = MagicMock()
        api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)
        with patch(
            "hummingbot.connector.exchange.backpack.backpack_web_utils.build_api_factory_without_time_synchronizer_pre_processor",
            return_value=api_factory,
        ):
            result = await web_utils.get_current_server_time()
        self.assertEqual(1_700_000_000_000.0, result)

    async def test_get_current_server_time_from_microseconds(self):
        rest_assistant = AsyncMock()
        rest_assistant.execute_request = AsyncMock(return_value=1_700_000_000_000_000)
        api_factory = MagicMock()
        api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)
        with patch(
            "hummingbot.connector.exchange.backpack.backpack_web_utils.build_api_factory_without_time_synchronizer_pre_processor",
            return_value=api_factory,
        ):
            result = await web_utils.get_current_server_time()
        self.assertEqual(1_700_000_000_000.0, result)

    async def test_get_current_server_time_invalid_value_fallback(self):
        rest_assistant = AsyncMock()
        rest_assistant.execute_request = AsyncMock(return_value={"serverTime": "not-a-number"})
        api_factory = MagicMock()
        api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)
        with patch(
            "hummingbot.connector.exchange.backpack.backpack_web_utils.build_api_factory_without_time_synchronizer_pre_processor",
            return_value=api_factory,
        ):
            with patch(
                "hummingbot.connector.exchange.backpack.backpack_web_utils.time.time",
                return_value=1,
            ):
                result = await web_utils.get_current_server_time()
        self.assertEqual(1_000_000.0, result)


if __name__ == "__main__":
    unittest.main()
