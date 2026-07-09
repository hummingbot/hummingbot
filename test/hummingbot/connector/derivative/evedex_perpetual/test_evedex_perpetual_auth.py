"""Unit tests for Evedex Perpetual authentication."""
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.evedex_perpetual.evedex_perpetual_auth import EvedexPerpetualAuth, to_eth_number
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSJSONRequest


class TestEvedexPerpetualAuth(unittest.TestCase):
    """
    Test suite for EvedexPerpetualAuth class.

    Evedex uses X-API-Key header for authentication as per Swagger API specification.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key-perpetual-12345"
        self.private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # noqa: mock
        self.time_provider = MagicMock()
        self.auth = EvedexPerpetualAuth(
            api_key=self.api_key,
            time_provider=self.time_provider,
            private_key=self.private_key
        )

    def test_auth_class_initialization(self):
        """Test that auth class initializes with API key and time provider."""
        self.assertEqual(self.auth._api_key, self.api_key)
        self.assertEqual(self.auth._time_provider, self.time_provider)

    def test_auth_class_initialization_with_private_key(self):
        """Test that auth class initializes wallet with private key."""
        self.assertIsNotNone(self.auth._wallet)
        self.assertEqual(len(self.auth._wallet.address), 42)  # Ethereum address length

    def test_header_for_authentication(self):
        """Test that auth headers include X-API-Key."""
        headers = self.auth.header_for_authentication()

        self.assertIn("X-API-Key", headers)
        self.assertEqual(headers["X-API-Key"], self.api_key)


class TestToEthNumber(unittest.TestCase):
    """Test suite for to_eth_number conversion function."""

    def test_to_eth_number_basic(self):
        """Test basic conversion with MATCHER_PRECISION of 8."""
        # 1.0 * 10^8 = 100000000
        result = to_eth_number(Decimal("1.0"))
        self.assertEqual(result, 100000000)

    def test_to_eth_number_with_decimals(self):
        """Test conversion with decimal values."""
        # 0.00000001 * 10^8 = 1
        result = to_eth_number(Decimal("0.00000001"))
        self.assertEqual(result, 1)

    def test_to_eth_number_large_value(self):
        """Test conversion with larger values."""
        # 50000.5 * 10^8 = 5000050000000
        result = to_eth_number(Decimal("50000.5"))
        self.assertEqual(result, 5000050000000)

    def test_to_eth_number_rounding(self):
        """Test that rounding uses ROUND_HALF_UP."""
        # 1.000000005 * 10^8 = 100000000.5 -> rounds to 100000001
        result = to_eth_number(Decimal("1.000000005"))
        self.assertEqual(result, 100000001)


class TestEvedexPerpetualAuthAsync(unittest.IsolatedAsyncioTestCase):
    """Async test suite for EvedexPerpetualAuth class."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test-api-key-async-perpetual-12345"
        self.private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # noqa: mock
        self.time_provider = MagicMock()
        self.auth = EvedexPerpetualAuth(
            api_key=self.api_key,
            time_provider=self.time_provider,
            private_key=self.private_key
        )

    async def test_rest_authenticate(self):
        """Test REST request authentication adds proper headers."""
        request = RESTRequest(
            method="GET",
            url="https://exchange-api.evedex.com/api/user/balance",
            headers={}
        )

        authenticated_request = await self.auth.rest_authenticate(request)

        self.assertIn("X-API-Key", authenticated_request.headers)
        self.assertEqual(authenticated_request.headers["X-API-Key"], self.api_key)

    async def test_rest_authenticate_preserves_existing_headers(self):
        """Test that authentication preserves existing headers."""
        existing_headers = {"Accept": "application/json", "Custom-Header": "custom-value"}
        request = RESTRequest(
            method="POST",
            url="https://exchange-api.evedex.com/api/v2/order/limit",
            headers=existing_headers
        )

        authenticated_request = await self.auth.rest_authenticate(request)

        # Check that existing headers are preserved
        self.assertEqual(authenticated_request.headers.get("Accept"), "application/json")
        self.assertEqual(authenticated_request.headers.get("Custom-Header"), "custom-value")
        # Check that auth header is added
        self.assertEqual(authenticated_request.headers["X-API-Key"], self.api_key)

    async def test_rest_authenticate_with_none_headers(self):
        """Test REST authentication when request has None headers."""
        request = RESTRequest(
            method="GET",
            url="https://exchange-api.evedex.com/api/position"
        )
        request.headers = None

        authenticated_request = await self.auth.rest_authenticate(request)

        self.assertIsNotNone(authenticated_request.headers)
        self.assertEqual(authenticated_request.headers["X-API-Key"], self.api_key)

    async def test_ws_authenticate_returns_request_unchanged(self):
        """Test that WS authenticate returns the request (auth is done via message)."""
        request = WSJSONRequest(payload={})
        authenticated_request = await self.auth.ws_authenticate(request)

        # WS auth is pass-through, request should be returned as-is
        self.assertEqual(request, authenticated_request)


class TestEvedexPerpetualAuthHeaderFormat(unittest.TestCase):
    """Test authentication header format matches Swagger API."""

    def test_auth_header_key_is_correct(self):
        """Test that the authentication header key is 'X-API-Key'."""
        auth = EvedexPerpetualAuth(api_key="test-key", time_provider=MagicMock())
        headers = auth.header_for_authentication()

        # Evedex uses X-API-Key header as documented in Swagger
        self.assertIn("X-API-Key", headers)
        # Should not have other auth headers like Authorization
        self.assertNotIn("Authorization", headers)

    def test_auth_header_value_is_api_key_directly(self):
        """Test that the header value is the API key directly (no Bearer prefix)."""
        api_key = "my-secret-api-key"
        auth = EvedexPerpetualAuth(api_key=api_key, time_provider=MagicMock())
        headers = auth.header_for_authentication()

        # Value should be API key directly, not "Bearer <key>"
        self.assertEqual(headers["X-API-Key"], api_key)
        self.assertNotIn("Bearer", headers["X-API-Key"])


class TestEvedexPerpetualAuthSigning(unittest.TestCase):
    def setUp(self):
        self.api_key = "test-api-key-signing"
        self.private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # noqa: mock
        self.time_provider = MagicMock()
        self.auth = EvedexPerpetualAuth(
            api_key=self.api_key,
            time_provider=self.time_provider,
            private_key=self.private_key
        )

    def test_wallet_address_property(self):
        self.assertIsNotNone(self.auth.wallet_address)
        self.assertTrue(self.auth.wallet_address.startswith("0x"))

    def test_wallet_address_none_without_private_key(self):
        auth = EvedexPerpetualAuth(api_key="test", time_provider=MagicMock())
        self.assertIsNone(auth.wallet_address)

    def test_sign_limit_order(self):
        signature = self.auth.sign_limit_order(
            order_id="OID1",
            instrument="XRPUSD",
            side="BUY",
            leverage=2,
            quantity=Decimal("1.5"),
            limit_price=Decimal("100.25"),
        )
        self.assertTrue(signature.startswith("0x"))

    def test_sign_market_order(self):
        signature = self.auth.sign_market_order(
            order_id="OID2",
            instrument="XRPUSD",
            side="SELL",
            time_in_force="IOC",
            leverage=3,
            cash_quantity=Decimal("250"),
        )
        self.assertTrue(signature.startswith("0x"))

    def test_sign_position_close(self):
        signature = self.auth.sign_position_close(
            order_id="OID3",
            instrument="XRPUSD",
            leverage=1,
            quantity=Decimal("2.5"),
        )
        self.assertTrue(signature.startswith("0x"))

    def test_sign_methods_require_private_key(self):
        auth = EvedexPerpetualAuth(api_key="test", time_provider=MagicMock())
        with self.assertRaises(ValueError):
            auth.sign_limit_order("OID", "XRPUSD", "BUY", 1, Decimal("1"), Decimal("1"))
        with self.assertRaises(ValueError):
            auth.sign_market_order("OID", "XRPUSD", "BUY", "IOC", 1, Decimal("1"))
        with self.assertRaises(ValueError):
            auth.sign_position_close("OID", "XRPUSD", 1, Decimal("1"))


class TestEvedexPerpetualAuthAccessTokenAsync(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api_key = "test-api-key-token"
        self.private_key = "0x0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # noqa: mock
        self.time_provider = MagicMock()
        self.auth = EvedexPerpetualAuth(
            api_key=self.api_key,
            time_provider=self.time_provider,
            private_key=self.private_key
        )

    async def test_get_access_token_uses_fetcher(self):
        self.auth.set_token_fetcher(AsyncMock(return_value={"token": "tok", "expireAt": 12345}))
        token = await self.auth.get_access_token()
        self.assertEqual(token, "tok")

    async def test_get_access_token_without_fetcher(self):
        token = await self.auth.get_access_token()
        self.assertEqual(token, "")


if __name__ == "__main__":
    unittest.main()
