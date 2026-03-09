"""
Tests for Bluefin Perpetual web utilities.

Tests URL construction, throttler creation, and web assistant factory.
"""
import unittest
from unittest.mock import MagicMock

from hummingbot.connector.derivative.bluefin_perpetual import bluefin_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_web_utils import (
    build_api_factory,
    create_throttler,
    get_rest_url_for_endpoint,
    get_ws_url,
)
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BluefinPerpetualWebUtilsTests(unittest.TestCase):
    """Test suite for Bluefin Perpetual web utilities."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

    def test_get_rest_url_for_endpoint_mainnet(self):
        """Test REST URL construction for mainnet."""
        endpoint = "/markets"
        url = get_rest_url_for_endpoint(endpoint, domain=CONSTANTS.DOMAIN)

        # Should contain mainnet environment name
        self.assertIn("sui-prod", url)
        self.assertIn(endpoint, url)
        self.assertTrue(url.startswith("https://"))

    def test_get_rest_url_for_endpoint_staging(self):
        """Test REST URL construction for staging."""
        endpoint = "/orders"
        url = get_rest_url_for_endpoint(endpoint, domain=CONSTANTS.STAGING_DOMAIN)

        # Should contain staging environment name
        self.assertIn("sui-staging", url)
        self.assertIn(endpoint, url)
        self.assertTrue(url.startswith("https://"))

    def test_get_ws_url_mainnet_market(self):
        """Test WebSocket URL construction for mainnet market stream."""
        url = get_ws_url(domain=CONSTANTS.DOMAIN, stream_type="market")

        # Should contain mainnet environment and market stream
        self.assertIn("sui-prod", url)
        self.assertIn("/ws/market", url)
        self.assertTrue(url.startswith("wss://"))

    def test_get_ws_url_mainnet_account(self):
        """Test WebSocket URL construction for mainnet account stream."""
        url = get_ws_url(domain=CONSTANTS.DOMAIN, stream_type="account")

        # Should contain mainnet environment and account stream
        self.assertIn("sui-prod", url)
        self.assertIn("/ws/account", url)
        self.assertTrue(url.startswith("wss://"))

    def test_get_ws_url_staging(self):
        """Test WebSocket URL construction for staging."""
        url = get_ws_url(domain=CONSTANTS.STAGING_DOMAIN, stream_type="market")

        # Should contain staging environment
        self.assertIn("sui-staging", url)
        self.assertTrue(url.startswith("wss://"))

    def test_create_throttler(self):
        """Test throttler creation."""
        throttler = create_throttler()

        # Should return valid throttler
        self.assertIsNotNone(throttler)
        # Should have rate limits configured
        self.assertIsNotNone(throttler._rate_limits)

    def test_build_api_factory_without_auth(self):
        """Test API factory creation without authentication."""
        factory = build_api_factory()

        # Should return WebAssistantsFactory
        self.assertIsInstance(factory, WebAssistantsFactory)
        self.assertIsNotNone(factory._throttler)

    def test_build_api_factory_with_custom_throttler(self):
        """Test API factory creation with custom throttler."""
        custom_throttler = create_throttler()
        factory = build_api_factory(throttler=custom_throttler)

        # Should use provided throttler
        self.assertIs(factory._throttler, custom_throttler)

    def test_build_api_factory_with_auth(self):
        """Test API factory creation with authentication."""
        mock_auth = MagicMock()
        factory = build_api_factory(auth=mock_auth)

        # Should include auth
        self.assertIs(factory._auth, mock_auth)

    def test_rest_url_service_variations(self):
        """Test REST URL construction with different services."""
        # Test api service (default)
        api_url = CONSTANTS.get_rest_url_for_env("sui-prod", service="api")
        self.assertIn("api.api.sui-prod", api_url)

        # Test auth service
        auth_url = CONSTANTS.get_rest_url_for_env("sui-prod", service="auth")
        self.assertIn("auth.api.sui-prod", auth_url)

        # Test trade service
        trade_url = CONSTANTS.get_rest_url_for_env("sui-prod", service="trade")
        self.assertIn("trade.api.sui-prod", trade_url)

    def test_ws_url_stream_type_variations(self):
        """Test WebSocket URL construction with different stream types."""
        # Test market stream
        market_url = CONSTANTS.get_ws_url_for_env("sui-prod", stream_type="market")
        self.assertIn("/ws/market", market_url)

        # Test account stream
        account_url = CONSTANTS.get_ws_url_for_env("sui-prod", stream_type="account")
        self.assertIn("/ws/account", account_url)
