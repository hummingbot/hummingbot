import asyncio
import hashlib
import hmac
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.derivative.true_perpetual.true_perpetual_auth import TruePerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class TruePerpetualAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "tbk_testkey"
        self.secret = "tbs_testsecret"
        self.time_provider = MagicMock()
        self.time_provider.time.return_value = 1700000000.123
        self.auth = TruePerpetualAuth(api_key=self.api_key, api_secret=self.secret, time_provider=self.time_provider)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def _expected_signature(self, timestamp: str, method: str, path_with_query: str, body: str) -> str:
        canonical = f"{timestamp}{method}{path_with_query}{body}"
        return hmac.new(self.secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    def test_configured(self):
        self.assertTrue(self.auth.configured)
        self.assertFalse(TruePerpetualAuth(api_key="", api_secret="", time_provider=self.time_provider).configured)
        self.assertFalse(TruePerpetualAuth(api_key=None, api_secret=None, time_provider=self.time_provider).configured)

    def test_path_with_query(self):
        self.assertEqual("/api/bot/v1/account", TruePerpetualAuth.path_with_query("https://app.truefinance.ai/api/bot/v1/account"))
        self.assertEqual(
            "/api/bot/v1/orders?market=BTCUSDC",
            TruePerpetualAuth.path_with_query("https://app.truefinance.ai/api/bot/v1/orders?market=BTCUSDC"))
        self.assertEqual("/", TruePerpetualAuth.path_with_query("https://app.truefinance.ai"))

    def test_rest_authenticate_get_folds_params_into_url_and_signs_them(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://app.truefinance.ai/api/bot/v1/orders",
            params={"market": "BTCUSDC"},
            is_auth_required=True,
        )
        signed = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual("https://app.truefinance.ai/api/bot/v1/orders?market=BTCUSDC", signed.url)
        self.assertIsNone(signed.params)
        self.assertEqual(self.api_key, signed.headers["X-TRUE-KEY"])
        self.assertEqual("1700000000123", signed.headers["X-TRUE-TS"])
        self.assertEqual(
            self._expected_signature("1700000000123", "GET", "/api/bot/v1/orders?market=BTCUSDC", ""),
            signed.headers["X-TRUE-SIGN"])
        self.assertNotIn("Content-Type", signed.headers)
        self.assertEqual("application/json", signed.headers["Accept"])

    def test_rest_authenticate_post_signs_exact_body_string(self):
        body = {"market": "BTCUSDC", "side": "buy", "type": "limit", "size": "0.001", "price": "50000"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://app.truefinance.ai/api/bot/v1/orders",
            data=body,
            is_auth_required=True,
        )
        signed = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        raw_body = json.dumps(body, separators=(",", ":"))
        self.assertEqual(raw_body, signed.data)
        self.assertEqual(
            self._expected_signature("1700000000123", "POST", "/api/bot/v1/orders", raw_body),
            signed.headers["X-TRUE-SIGN"])
        self.assertEqual("application/json", signed.headers["Content-Type"])

    def test_rest_authenticate_post_with_string_body_keeps_it(self):
        raw_body = '{"market":"BTCUSDC"}'
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://app.truefinance.ai/api/bot/v1/ws-token",
            data=raw_body,
            is_auth_required=True,
        )
        signed = self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertEqual(raw_body, signed.data)
        self.assertEqual(
            self._expected_signature("1700000000123", "POST", "/api/bot/v1/ws-token", raw_body),
            signed.headers["X-TRUE-SIGN"])

    def test_rest_authenticate_delete_with_query(self):
        request = RESTRequest(
            method=RESTMethod.DELETE,
            url="https://app.truefinance.ai/api/bot/v1/orders/123",
            params={"market": "ETHUSDC"},
            is_auth_required=True,
        )
        signed = self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertEqual(
            self._expected_signature("1700000000123", "DELETE", "/api/bot/v1/orders/123?market=ETHUSDC", ""),
            signed.headers["X-TRUE-SIGN"])

    def test_sign_headers_is_deterministic(self):
        first = self.auth.sign_headers("1", "GET", "/api/bot/v1/time", "")
        second = self.auth.sign_headers("1", "GET", "/api/bot/v1/time", "")
        self.assertEqual(first, second)
        self.assertEqual({"X-TRUE-KEY", "X-TRUE-TS", "X-TRUE-SIGN"}, set(first.keys()))

    def test_ws_authenticate_is_passthrough(self):
        request = WSJSONRequest(payload={"op": "subscribe", "args": ["orderbook:BTCUSDC"]})
        signed = self.async_run_with_timeout(self.auth.ws_authenticate(request))
        self.assertIs(request, signed)
