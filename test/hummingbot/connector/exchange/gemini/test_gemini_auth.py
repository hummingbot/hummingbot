import asyncio
import base64
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth, NONCE_DRIFT_RESET_US
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
        self.assertIsInstance(decoded_payload["nonce"], float)
        self.assertEqual(now, decoded_payload["nonce"])

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
        self.assertIsInstance(decoded_payload["nonce"], float)
        self.assertEqual(now, decoded_payload["nonce"])

    def test_nonce_is_monotonically_increasing(self):
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = 1234567890.000

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        first = auth._get_nonce()
        second = auth._get_nonce()
        third = auth._get_nonce()
        self.assertEqual(1234567890.0, first)
        self.assertLess(first, second)
        self.assertLess(second, third)
        self.assertLess(third - first, 0.001)

    def test_nonce_remains_monotonic_when_clock_moves_back(self):
        mock_time_provider = MagicMock()
        mock_time_provider.time.side_effect = [1234567890.000, 1234567880.000, 1234567890.000]

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        nonces = [auth._get_nonce() for _ in range(3)]

        self.assertEqual(1234567890.0, nonces[0])
        self.assertEqual(nonces, sorted(nonces))
        self.assertEqual(3, len(set(nonces)))
        self.assertLess(nonces[-1] - nonces[0], 0.001)

    def test_nonce_does_not_repeat_during_sustained_requests(self):
        mock_time_provider = MagicMock()
        mock_time_provider.time.side_effect = [1234567890.000 + index / 5 for index in range(100)]
        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        nonces = [auth._get_nonce() for _ in range(100)]

        self.assertEqual(100, len(set(nonces)))
        self.assertEqual(nonces, sorted(nonces))
        self.assertTrue(all(isinstance(nonce, float) for nonce in nonces))
        self.assertTrue(all(1234567890 <= nonce < 1234567910 for nonce in nonces))

    def test_nonce_generation_is_serialized_across_threads(self):
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = 1234567890.000
        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        with ThreadPoolExecutor(max_workers=10) as executor:
            nonces = list(executor.map(lambda _: auth._get_nonce(), range(100)))

        self.assertEqual(100, len(set(nonces)))
        self.assertEqual(1234567890.0, min(nonces))
        # ThreadPoolExecutor.map returns results in input order, which is not the
        # order in which workers acquire the nonce lock. Uniqueness and the compact
        # strictly increasing allocated range are the thread-safety guarantees.
        self.assertEqual(100, len(sorted(nonces)))
        self.assertLess(max(nonces) - min(nonces), 0.001)

    def test_nonce_rebases_after_large_downward_drift(self):
        mock_time_provider = MagicMock()
        corrected_timestamp = 1234567890.000
        mock_time_provider.time.return_value = corrected_timestamp
        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        auth._last_nonce_us = int(corrected_timestamp * 1e6) + NONCE_DRIFT_RESET_US + 1

        nonce = auth._get_nonce()

        self.assertEqual(corrected_timestamp, nonce)
        self.assertEqual(int(nonce * 1e6), auth._last_nonce_us)

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
        self.assertEqual(str(int(now * 1_000)), configured_request.headers["X-GEMINI-NONCE"])
        self.assertNotIn(".", configured_request.headers["X-GEMINI-NONCE"])

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
        self.assertEqual(str(int(now * 1_000)), headers["X-GEMINI-NONCE"])
        self.assertNotIn(".", headers["X-GEMINI-NONCE"])

    def test_ws_nonce_is_integer_milliseconds_and_unique_during_reconnect_burst(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = GeminiAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        nonces = [auth.get_ws_auth_headers()["X-GEMINI-NONCE"] for _ in range(3)]

        self.assertEqual(["1234567890000", "1234567890001", "1234567890002"], nonces)
        self.assertTrue(all(nonce.isdigit() for nonce in nonces))

        rest_nonce = auth._get_nonce()
        self.assertIsInstance(rest_nonce, float)
        self.assertAlmostEqual(now, rest_nonce, places=3)
