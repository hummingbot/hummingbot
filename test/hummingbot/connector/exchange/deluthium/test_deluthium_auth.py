"""
Unit tests for Deluthium authentication.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock

from hummingbot.connector.exchange.deluthium.deluthium_auth import DeluthiumAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TestDeluthiumAuth(unittest.TestCase):
    """Test cases for DeluthiumAuth class."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_jwt_token_12345"
        self.auth = DeluthiumAuth(api_key=self.api_key)

    def test_api_key_property(self):
        """Test api_key property returns correct value."""
        self.assertEqual(self.auth.api_key, self.api_key)

    def test_get_auth_headers(self):
        """Test that auth headers are correctly generated."""
        headers = self.auth.get_auth_headers()
        
        self.assertIn("Authorization", headers)
        self.assertIn("Content-Type", headers)
        self.assertEqual(headers["Authorization"], f"Bearer {self.api_key}")
        self.assertEqual(headers["Content-Type"], "application/json")

    async def test_rest_authenticate(self):
        """Test REST request authentication."""
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://rfq-api.deluthium.ai/v1/listing/pairs",
            headers={}
        )
        
        authenticated_request = await self.auth.rest_authenticate(request)
        
        self.assertIn("Authorization", authenticated_request.headers)
        self.assertEqual(
            authenticated_request.headers["Authorization"],
            f"Bearer {self.api_key}"
        )

    async def test_rest_authenticate_preserves_existing_headers(self):
        """Test that authentication preserves existing headers."""
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://rfq-api.deluthium.ai/v1/quote/firm",
            headers={"X-Custom-Header": "custom_value"}
        )
        
        authenticated_request = await self.auth.rest_authenticate(request)
        
        self.assertIn("Authorization", authenticated_request.headers)
        self.assertIn("X-Custom-Header", authenticated_request.headers)
        self.assertEqual(
            authenticated_request.headers["X-Custom-Header"],
            "custom_value"
        )

    async def test_ws_authenticate_passthrough(self):
        """Test that WebSocket authentication is pass-through."""
        from hummingbot.core.web_assistant.connections.data_types import WSRequest
        
        request = WSRequest(payload={"test": "data"})
        result = await self.auth.ws_authenticate(request)
        
        # Should return the same request unchanged
        self.assertEqual(result.payload, {"test": "data"})


class TestDeluthiumAuthAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for DeluthiumAuth class."""

    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_jwt_token_async"
        self.auth = DeluthiumAuth(api_key=self.api_key)

    async def test_rest_authenticate_async(self):
        """Test async REST authentication."""
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://rfq-api.deluthium.ai/v1/listing/pairs"
        )
        
        result = await self.auth.rest_authenticate(request)
        
        self.assertIsNotNone(result.headers)
        self.assertIn("Authorization", result.headers)


if __name__ == "__main__":
    unittest.main()
