import asyncio
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GRVTPerpetualAuth


class GRVTPerpetualAuthTests(TestCase):
    def setUp(self):
        self.auth = GRVTPerpetualAuth(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )

    def test_header_for_authentication(self):
        headers = self.auth.header_for_authentication()
        self.assertEqual("test_api_key", headers.get("GRVT-API-KEY"))

    def test_get_auth_headers(self):
        headers = self.auth.get_auth_headers()
        self.assertIn("GRVT-API-KEY", headers)
        self.assertIn("GRVT-TIMESTAMP", headers)
        self.assertIn("GRVT-SIGNATURE", headers)

    def test_generate_signature(self):
        signature = self.auth.generate_signature(
            method="GET",
            path="/test",
            params={"key": "value"}
        )
        self.assertIsNotNone(signature)
        self.assertIsInstance(signature, str)
        self.assertEqual(64, len(signature))  # SHA256 hex digest is 64 chars

    def test_generate_signature_with_empty_params(self):
        signature = self.auth.generate_signature(
            method="GET",
            path="/test",
            params=None
        )
        self.assertIsNotNone(signature)
        self.assertIsInstance(signature, str)


class GRVTPerpetualAuthAsyncTests(TestCase):
    def setUp(self):
        self.auth = GRVTPerpetualAuth(
            api_key="test_api_key",
            api_secret="test_api_secret"
        )

    def async_run_with_timeout(self, coroutine, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_rest_authenticate(self):
        from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
        
        request = RESTRequest(
            url="https://api.grvt.io/test",
            method=RESTMethod.GET,
        )
        
        authenticated_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))
        
        self.assertIn("GRVT-API-KEY", authenticated_request.headers)
        self.assertIn("GRVT-TIMESTAMP", authenticated_request.headers)
        self.assertIn("GRVT-SIGNATURE", authenticated_request.headers)

    def test_ws_authenticate(self):
        from hummingbot.core.web_assistant.connections.data_types import WSRequest
        
        request = WSRequest()
        
        # WebSocket auth should return the request as-is (handled differently)
        authenticated_request = self.async_run_with_timeout(self.auth.ws_authenticate(request))
        
        # No additional headers added for WS (handled via URL params)
        self.assertEqual(request, authenticated_request)
