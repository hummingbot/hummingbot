import asyncio
import base64
import hashlib
import hmac
import json
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class GeminiAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "testSecret"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        params = {
            "request": "/v1/order/new",
            "symbol": "btcusd",
            "amount": "1.0",
            "price": "50000.00",
            "side": "buy",
            "type": "exchange limit",
        }

        request = RESTRequest(
            method=RESTMethod.POST,
            data=json.dumps(params),
            is_auth_required=True,
        )
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        # Verify headers are set
        self.assertIn("X-GEMINI-APIKEY", configured_request.headers)
        self.assertIn("X-GEMINI-PAYLOAD", configured_request.headers)
        self.assertIn("X-GEMINI-SIGNATURE", configured_request.headers)
        self.assertEqual(self._api_key, configured_request.headers["X-GEMINI-APIKEY"])

        # Verify signature
        payload_b64 = configured_request.headers["X-GEMINI-PAYLOAD"]
        expected_signature = hmac.new(
            self._secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha384
        ).hexdigest()
        self.assertEqual(expected_signature, configured_request.headers["X-GEMINI-SIGNATURE"])

        # Verify payload contains nonce
        decoded_payload = json.loads(base64.b64decode(payload_b64))
        self.assertIn("nonce", decoded_payload)
        self.assertEqual(int(now * 1000), decoded_payload["nonce"])

        # Verify body is cleared (Gemini uses headers, not body)
        self.assertIsNone(configured_request.data)

    def test_ws_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        request = MagicMock()
        request.headers = None
        configured_request = self.async_run_with_timeout(auth.ws_authenticate(request))

        self.assertIn("X-GEMINI-APIKEY", configured_request.headers)
        self.assertIn("X-GEMINI-NONCE", configured_request.headers)
        self.assertIn("X-GEMINI-PAYLOAD", configured_request.headers)
        self.assertIn("X-GEMINI-SIGNATURE", configured_request.headers)

        self.assertEqual(self._api_key, configured_request.headers["X-GEMINI-APIKEY"])

        # Verify WS signature
        nonce = configured_request.headers["X-GEMINI-NONCE"]
        payload_b64 = base64.b64encode(nonce.encode("utf-8")).decode("utf-8")
        expected_signature = hmac.new(
            self._secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha384
        ).hexdigest()
        self.assertEqual(expected_signature, configured_request.headers["X-GEMINI-SIGNATURE"])

    def test_get_ws_auth_headers(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        headers = auth.get_ws_auth_headers()

        self.assertIn("X-GEMINI-APIKEY", headers)
        self.assertIn("X-GEMINI-NONCE", headers)
        self.assertIn("X-GEMINI-PAYLOAD", headers)
        self.assertIn("X-GEMINI-SIGNATURE", headers)
        self.assertEqual(self._api_key, headers["X-GEMINI-APIKEY"])
