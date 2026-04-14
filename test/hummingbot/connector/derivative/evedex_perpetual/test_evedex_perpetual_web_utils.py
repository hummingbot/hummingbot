"""Unit tests for Evedex Perpetual web utilities module."""
import unittest
from unittest.mock import MagicMock

from hummingbot.connector.derivative.evedex_perpetual import (
    evedex_perpetual_constants as CONSTANTS,
    evedex_perpetual_web_utils as web_utils,
)
from hummingbot.core.web_assistant.connections.data_types import RESTRequest


class TestEvedexPerpetualWebUtils(unittest.TestCase):
    """Test suite for Evedex Perpetual web utility functions."""

    def test_public_rest_url(self):
        """Test public REST URL construction."""
        path = "/api/market/instrument"
        url = web_utils.public_rest_url(path)

        expected = f"{CONSTANTS.REST_URL}{path}"
        self.assertEqual(url, expected)

    def test_public_rest_url_with_domain(self):
        """Test public REST URL with domain parameter."""
        path = "/api/market/instrument"
        url = web_utils.public_rest_url(path, domain="test_domain")

        expected = f"{CONSTANTS.REST_URL}{path}"
        self.assertEqual(url, expected)

    def test_private_rest_url(self):
        """Test private REST URL construction."""
        path = "/api/user/balance"
        url = web_utils.private_rest_url(path)

        expected = f"{CONSTANTS.REST_URL}{path}"
        self.assertEqual(url, expected)

    def test_private_rest_url_with_domain(self):
        """Test private REST URL with domain parameter."""
        path = "/api/user/balance"
        url = web_utils.private_rest_url(path, domain="test_domain")

        expected = f"{CONSTANTS.REST_URL}{path}"
        self.assertEqual(url, expected)

    def test_wss_url(self):
        """Test WebSocket URL."""
        url = web_utils.wss_url()
        self.assertEqual(url, CONSTANTS.WSS_URL)

    def test_wss_url_with_domain(self):
        """Test WebSocket URL with domain parameter."""
        url = web_utils.wss_url(domain="test_domain")
        self.assertEqual(url, CONSTANTS.WSS_URL)

    def test_create_throttler(self):
        """Test throttler creation with rate limits."""
        throttler = web_utils.create_throttler()

        self.assertIsNotNone(throttler)

    def test_build_api_factory(self):
        """Test API factory creation."""
        api_factory = web_utils.build_api_factory()

        self.assertIsNotNone(api_factory)

    def test_build_api_factory_with_auth(self):
        """Test API factory creation with authentication."""
        mock_auth = MagicMock()
        api_factory = web_utils.build_api_factory(auth=mock_auth)

        self.assertIsNotNone(api_factory)

    def test_build_api_factory_without_time_synchronizer(self):
        """Test API factory creation without time synchronizer."""
        throttler = web_utils.create_throttler()
        api_factory = web_utils.build_api_factory_without_time_synchronizer_pre_processor(throttler)

        self.assertIsNotNone(api_factory)


class TestEvedexPerpetualRESTPreProcessor(unittest.IsolatedAsyncioTestCase):
    """Test suite for EvedexPerpetualRESTPreProcessor."""

    async def test_pre_process_adds_content_type(self):
        """Test that pre-processor adds Content-Type header."""
        pre_processor = web_utils.EvedexPerpetualRESTPreProcessor()
        request = RESTRequest(
            method="GET",
            url="https://exchange-api.evedex.com/api/market/instrument"
        )

        processed_request = await pre_processor.pre_process(request)

        self.assertIn("Content-Type", processed_request.headers)
        self.assertEqual(processed_request.headers["Content-Type"], "application/json")

    async def test_pre_process_preserves_existing_headers(self):
        """Test that pre-processor preserves existing headers."""
        pre_processor = web_utils.EvedexPerpetualRESTPreProcessor()
        request = RESTRequest(
            method="GET",
            url="https://exchange-api.evedex.com/api/position",
            headers={"X-Custom-Header": "custom-value"}
        )

        processed_request = await pre_processor.pre_process(request)

        self.assertEqual(processed_request.headers["X-Custom-Header"], "custom-value")
        self.assertEqual(processed_request.headers["Content-Type"], "application/json")

    async def test_pre_process_with_none_headers(self):
        """Test that pre-processor handles None headers."""
        pre_processor = web_utils.EvedexPerpetualRESTPreProcessor()
        request = RESTRequest(
            method="POST",
            url="https://exchange-api.evedex.com/api/v2/order/limit"
        )
        request.headers = None

        processed_request = await pre_processor.pre_process(request)

        self.assertIsNotNone(processed_request.headers)
        self.assertEqual(processed_request.headers["Content-Type"], "application/json")


class TestEvedexPerpetualURLConstants(unittest.TestCase):
    """Test URL constants match official Evedex API."""

    def test_rest_url(self):
        """Test REST base URL."""
        self.assertEqual(CONSTANTS.REST_URL, "https://exchange-api.evedex.com")

    def test_wss_url(self):
        """Test WebSocket URL (Centrifugo endpoint)."""
        self.assertEqual(CONSTANTS.WSS_URL, "wss://ws.evedex.com/connection/websocket")

    def test_market_api_paths(self):
        """Test market API path constants match Swagger API."""
        self.assertEqual(CONSTANTS.INSTRUMENTS_PATH_URL, "/api/market/instrument")
        self.assertEqual(CONSTANTS.ORDER_BOOK_PATH_URL, "/api/market/{instrument}/deep")
        self.assertEqual(CONSTANTS.PING_PATH_URL, "/api/ping")

    def test_order_api_paths(self):
        """Test order API path constants match Swagger API."""
        self.assertEqual(CONSTANTS.LIMIT_ORDER_PATH_URL, "/api/v2/order/limit")
        self.assertEqual(CONSTANTS.MARKET_ORDER_PATH_URL, "/api/v2/order/market")
        self.assertEqual(CONSTANTS.CANCEL_ORDER_PATH_URL, "/api/order/{orderId}")
        self.assertEqual(CONSTANTS.GET_ORDER_PATH_URL, "/api/order/{orderId}")

    def test_user_api_paths(self):
        """Test user API path constants match Swagger API."""
        self.assertEqual(CONSTANTS.USER_BALANCE_PATH_URL, "/api/user/balance")
        self.assertEqual(CONSTANTS.USER_ME_PATH_URL, "/api/user/me")

    def test_position_api_paths(self):
        """Test position API path constants match Swagger API."""
        self.assertEqual(CONSTANTS.POSITIONS_PATH_URL, "/api/position")


class TestURLFormatting(unittest.TestCase):
    """Test URL formatting for various API calls."""

    def test_order_book_url_format(self):
        """Test order book URL formatting with instrument parameter."""
        instrument = "BTC-USDT"
        path = CONSTANTS.ORDER_BOOK_PATH_URL.format(instrument=instrument)
        url = web_utils.public_rest_url(path)

        expected = f"{CONSTANTS.REST_URL}/api/market/{instrument}/deep"
        self.assertEqual(url, expected)

    def test_cancel_order_url_format(self):
        """Test cancel order URL formatting with orderId parameter."""
        order_id = "00001:00000000000000000000000001"
        path = CONSTANTS.CANCEL_ORDER_PATH_URL.format(orderId=order_id)
        url = web_utils.private_rest_url(path)

        expected = f"{CONSTANTS.REST_URL}/api/order/{order_id}"
        self.assertEqual(url, expected)

    def test_get_order_url_format(self):
        """Test get order URL formatting with orderId parameter."""
        order_id = "00001:00000000000000000000000001"
        path = CONSTANTS.GET_ORDER_PATH_URL.format(orderId=order_id)
        url = web_utils.private_rest_url(path)

        expected = f"{CONSTANTS.REST_URL}/api/order/{order_id}"
        self.assertEqual(url, expected)

    def test_close_position_url_format(self):
        """Test close position URL formatting with instrument parameter."""
        instrument = "BTC-USDT"
        path = CONSTANTS.CLOSE_POSITION_PATH_URL.format(instrument=instrument)
        url = web_utils.private_rest_url(path)

        expected = f"{CONSTANTS.REST_URL}/api/v2/position/{instrument}/close"
        self.assertEqual(url, expected)

    def test_set_leverage_url_format(self):
        """Test set leverage URL formatting with instrument parameter."""
        instrument = "BTC-USDT"
        path = CONSTANTS.SET_LEVERAGE_PATH_URL.format(instrument=instrument)
        url = web_utils.private_rest_url(path)

        expected = f"{CONSTANTS.REST_URL}/api/position/{instrument}"
        self.assertEqual(url, expected)


if __name__ == "__main__":
    unittest.main()
