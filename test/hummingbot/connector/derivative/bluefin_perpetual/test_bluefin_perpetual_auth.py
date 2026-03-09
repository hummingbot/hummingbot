"""
Tests for Bluefin Perpetual authentication.

Since the Bluefin SDK handles authentication internally via JWT tokens,
these tests verify the auth wrapper properly stores credentials.
"""
import asyncio
import unittest
from typing import Awaitable
from unittest.mock import MagicMock

from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_auth import BluefinPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class BluefinPerpetualAuthTests(unittest.TestCase):
    """Test suite for BluefinPerpetualAuth class."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.test_mnemonic = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"
        self.test_network = "MAINNET"
        self.auth = BluefinPerpetualAuth(
            wallet_mnemonic=self.test_mnemonic,
            network=self.test_network,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        """Run async coroutine with timeout."""
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_wallet_mnemonic_property(self):
        """Test that wallet mnemonic is stored correctly."""
        self.assertEqual(self.test_mnemonic, self.auth.wallet_mnemonic)

    def test_network_property(self):
        """Test that network is stored correctly."""
        self.assertEqual(self.test_network, self.auth.network)

    def test_rest_authenticate_passes_through(self):
        """Test that REST authenticate returns request unchanged (SDK handles auth)."""
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/orders",
            data='{"symbol": "BTC-PERP"}',
            is_auth_required=True,
        )

        authenticated_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        # Should return the same request unchanged
        self.assertEqual(request, authenticated_request)
        self.assertEqual(request.url, authenticated_request.url)
        self.assertEqual(request.data, authenticated_request.data)

    def test_get_headers_returns_empty_dict(self):
        """Test that get_headers returns empty dict (SDK manages JWT headers)."""
        headers = self.auth.get_headers()

        self.assertEqual({}, headers)
        self.assertIsInstance(headers, dict)

    def test_auth_with_staging_network(self):
        """Test authentication with STAGING network."""
        staging_auth = BluefinPerpetualAuth(
            wallet_mnemonic=self.test_mnemonic,
            network="STAGING",
        )

        self.assertEqual("STAGING", staging_auth.network)
        self.assertEqual(self.test_mnemonic, staging_auth.wallet_mnemonic)
