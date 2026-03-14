import unittest
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class TestDecibelPerpetualAuth(unittest.IsolatedAsyncioTestCase):
    """Unit tests for DecibelPerpetualAuth."""

    def setUp(self):
        self.auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xdeadbeef" * 8,
            main_wallet_public_key="0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            api_key="test_bearer_token",
        )

    # ------------------------------------------------------------------
    # Test 1: main_wallet_address property
    # ------------------------------------------------------------------
    def test_main_wallet_address(self):
        address = self.auth.main_wallet_address
        self.assertEqual(
            address,
            "0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        )

    # ------------------------------------------------------------------
    # Test 2: api_key property
    # ------------------------------------------------------------------
    def test_api_key_property(self):
        self.assertEqual(self.auth.api_key, "test_bearer_token")

    # ------------------------------------------------------------------
    # Test 3: get_auth_headers returns Authorization header
    # ------------------------------------------------------------------
    def test_get_auth_headers_with_api_key(self):
        headers = self.auth.get_auth_headers()
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer test_bearer_token")

    # ------------------------------------------------------------------
    # Test 4: get_auth_headers returns empty dict when no api_key
    # ------------------------------------------------------------------
    def test_get_auth_headers_without_api_key(self):
        auth_no_key = DecibelPerpetualAuth(
            api_wallet_private_key="0xkey",
            main_wallet_public_key="0xaddr",
            api_key="",
        )
        headers = auth_no_key.get_auth_headers()
        self.assertEqual(headers, {})

    # ------------------------------------------------------------------
    # Test 5: rest_authenticate injects Bearer header
    # ------------------------------------------------------------------
    async def test_rest_authenticate_adds_authorization_header(self):
        request = RESTRequest(method=RESTMethod.GET, url="https://example.com")
        authenticated = await self.auth.rest_authenticate(request)
        self.assertIsNotNone(authenticated.headers)
        self.assertEqual(authenticated.headers["Authorization"], "Bearer test_bearer_token")

    # ------------------------------------------------------------------
    # Test 6: rest_authenticate merges with existing headers
    # ------------------------------------------------------------------
    async def test_rest_authenticate_preserves_existing_headers(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://example.com",
            headers={"Content-Type": "application/json"},
        )
        authenticated = await self.auth.rest_authenticate(request)
        self.assertEqual(authenticated.headers["Content-Type"], "application/json")
        self.assertEqual(authenticated.headers["Authorization"], "Bearer test_bearer_token")

    # ------------------------------------------------------------------
    # Test 7: rest_authenticate does not add header when api_key empty
    # ------------------------------------------------------------------
    async def test_rest_authenticate_no_header_without_key(self):
        auth_no_key = DecibelPerpetualAuth(
            api_wallet_private_key="0xkey",
            main_wallet_public_key="0xaddr",
            api_key="",
        )
        request = RESTRequest(method=RESTMethod.GET, url="https://example.com")
        authenticated = await auth_no_key.rest_authenticate(request)
        # headers should remain None or not contain Authorization
        if authenticated.headers:
            self.assertNotIn("Authorization", authenticated.headers)

    # ------------------------------------------------------------------
    # Test 8: ws_authenticate returns request unchanged
    # ------------------------------------------------------------------
    async def test_ws_authenticate_returns_request_unchanged(self):
        ws_request = WSRequest(payload={"test": "data"})
        result = await self.auth.ws_authenticate(ws_request)
        self.assertIs(result, ws_request)

    # ------------------------------------------------------------------
    # Test 9: get_private_key returns raw private key
    # ------------------------------------------------------------------
    def test_get_private_key(self):
        self.assertEqual(self.auth.get_private_key(), "0xdeadbeef" * 8)

    # ------------------------------------------------------------------
    # Test 10: api_wallet_address is 0x-prefixed
    # ------------------------------------------------------------------
    def test_api_wallet_address_prefix(self):
        auth = DecibelPerpetualAuth(
            api_wallet_private_key="0xkey",
            main_wallet_public_key="abcdef",
            api_key="key",
        )
        # api_wallet_address uses main wallet public key internally
        self.assertTrue(auth.api_wallet_address.startswith("0x"))


if __name__ == "__main__":
    unittest.main()
