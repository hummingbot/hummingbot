import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.backpack_perpetual import (
    backpack_perpetual_constants as CONSTANTS,
    backpack_perpetual_web_utils as web_utils,
)


class TestBackpackPerpetualWebUtils(unittest.TestCase):
    """Test cases for backpack_perpetual_web_utils module."""

    def test_rest_url_mainnet(self):
        """Test REST URL generation for mainnet."""
        url = web_utils.rest_url("/api/v1/markets")
        expected = f"{CONSTANTS.BASE_URL}/api/v1/markets"
        self.assertEqual(expected, url)

    def test_rest_url_testnet(self):
        """Test REST URL generation for testnet."""
        url = web_utils.rest_url("/api/v1/markets", domain=CONSTANTS.TESTNET_DOMAIN)
        expected = f"{CONSTANTS.TESTNET_BASE_URL}/api/v1/markets"
        self.assertEqual(expected, url)

    def test_wss_url_mainnet(self):
        """Test WebSocket URL generation for mainnet."""
        url = web_utils.wss_url()
        self.assertEqual(CONSTANTS.WS_URL, url)

    def test_wss_url_testnet(self):
        """Test WebSocket URL generation for testnet."""
        url = web_utils.wss_url(domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(CONSTANTS.TESTNET_WS_URL, url)

    def test_build_api_factory(self):
        """Test API factory creation."""
        factory = web_utils.build_api_factory()
        self.assertIsNotNone(factory)

    def test_build_api_factory_with_throttler(self):
        """Test API factory creation with throttler."""
        from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
        throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        factory = web_utils.build_api_factory(throttler=throttler)
        self.assertIsNotNone(factory)

    def test_rest_url_with_all_endpoints(self):
        """Test REST URL generation for all defined endpoints."""
        endpoints = [
            CONSTANTS.MARKETS_URL,
            CONSTANTS.TICKER_URL,
            CONSTANTS.DEPTH_URL,
            CONSTANTS.TRADES_URL,
            CONSTANTS.CAPITAL_URL,
            CONSTANTS.ORDER_URL,
            CONSTANTS.POSITION_URL,
            CONSTANTS.POSITIONS_URL,
            CONSTANTS.LEVERAGE_URL,
            CONSTANTS.FUNDING_RATES_URL,
            CONSTANTS.MARK_PRICES_URL,
        ]

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                url = web_utils.rest_url(endpoint)
                self.assertTrue(url.startswith(CONSTANTS.BASE_URL))
                self.assertTrue(endpoint in url)


class TestBackpackPerpetualWebUtilsAsync(IsolatedAsyncioWrapperTestCase):
    async def test_get_current_server_time_from_seconds(self):
        rest_assistant = AsyncMock()
        rest_assistant.execute_request = AsyncMock(return_value={"serverTime": "1700000000"})
        api_factory = MagicMock()
        api_factory.get_rest_assistant = AsyncMock(return_value=rest_assistant)
        with patch(
            "hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_web_utils.build_api_factory_without_time_synchronizer_pre_processor",
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
            "hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_web_utils.build_api_factory_without_time_synchronizer_pre_processor",
            return_value=api_factory,
        ):
            result = await web_utils.get_current_server_time()
        self.assertEqual(1_700_000_000_000.0, result)


if __name__ == "__main__":
    unittest.main()
