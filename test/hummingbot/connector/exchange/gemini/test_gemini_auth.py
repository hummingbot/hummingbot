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
        self.assertEqual(int(now), decoded_payload["nonce"])

        # Verify body is cleared (Gemini uses headers, not body)
        self.assertIsNone(configured_request.data)

    def test_rest_authenticate_with_dict_data_and_existing_headers(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        request = RESTRequest(
            method=RESTMethod.POST,
            data={"request": "/v1/balances"},
            headers={"X-Custom": "keep-me"},
            is_auth_required=True,
        )
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        # Pre-existing headers must be preserved
        self.assertEqual("keep-me", configured_request.headers["X-Custom"])
        decoded_payload = json.loads(base64.b64decode(configured_request.headers["X-GEMINI-PAYLOAD"]))
        self.assertEqual("/v1/balances", decoded_payload["request"])
        self.assertEqual(int(now), decoded_payload["nonce"])

    def test_nonce_is_monotonically_increasing(self):
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = 1234567890.000

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        first = auth._get_nonce()
        second = auth._get_nonce()
        third = auth._get_nonce()
        self.assertEqual(1234567890, first)
        self.assertEqual(1234567891, second)
        self.assertEqual(1234567892, third)

    def test_nonce_resets_when_counter_drifts_ahead(self):
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = 1234567890.000

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        # Simulate a counter that drifted far ahead of current time (e.g. clock correction)
        auth._last_nonce = 1234567890 + 100
        nonce = auth._get_nonce()
        self.assertEqual(1234567890, nonce)

    def test_nonce_uses_local_time_without_provider(self):
        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=None)
        nonce = auth._get_nonce()
        self.assertGreater(nonce, 0)

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
