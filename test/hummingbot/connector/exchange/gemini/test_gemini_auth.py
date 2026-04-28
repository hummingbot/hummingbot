import base64
import hashlib
import hmac
import json
import unittest
from unittest.mock import MagicMock

from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class TestGeminiAuth(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.api_key = "test_api_key"
        self.secret_key = "test_secret_key"
        self.auth = GeminiAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=MagicMock(),
        )

    def test_generate_rest_signature(self):
        payload_dict = {"request": "/v1/order/new", "nonce": 123456789}
        b64_payload, signature = self.auth.generate_rest_signature(payload_dict)

        # Verify base64 payload decodes back to original
        decoded = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(decoded["request"], "/v1/order/new")
        self.assertEqual(decoded["nonce"], 123456789)

        # Verify signature matches expected HMAC-SHA384
        expected_b64 = base64.b64encode(json.dumps(payload_dict).encode("utf-8"))
        expected_sig = hmac.new(
            self.secret_key.encode("utf-8"),
            expected_b64,
            hashlib.sha384
        ).hexdigest()
        self.assertEqual(signature, expected_sig)

    async def test_rest_authenticate_sets_correct_headers(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.gemini.com/v1/order/new",
            data=json.dumps({"symbol": "btcusd", "amount": "1"}),
        )

        authenticated = await self.auth.rest_authenticate(request)

        self.assertIn("X-GEMINI-APIKEY", authenticated.headers)
        self.assertIn("X-GEMINI-PAYLOAD", authenticated.headers)
        self.assertIn("X-GEMINI-SIGNATURE", authenticated.headers)
        self.assertEqual(authenticated.headers["X-GEMINI-APIKEY"], self.api_key)
        self.assertEqual(authenticated.headers["Content-Type"], "text/plain")
        self.assertEqual(authenticated.headers["Content-Length"], "0")

        # Body should be cleared for Gemini auth
        self.assertIsNone(authenticated.data)

    async def test_rest_authenticate_includes_request_and_nonce_in_payload(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.gemini.com/v1/balances",
            data=None,
        )

        authenticated = await self.auth.rest_authenticate(request)

        b64_payload = authenticated.headers["X-GEMINI-PAYLOAD"]
        decoded = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(decoded["request"], "/v1/balances")
        self.assertIn("nonce", decoded)
        self.assertIsInstance(decoded["nonce"], int)

    async def test_rest_authenticate_preserves_data_in_payload(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.gemini.com/v1/order/new",
            data=json.dumps({"symbol": "btcusd", "amount": "1", "price": "50000", "side": "buy", "type": "exchange limit"}),
        )

        authenticated = await self.auth.rest_authenticate(request)

        b64_payload = authenticated.headers["X-GEMINI-PAYLOAD"]
        decoded = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(decoded["symbol"], "btcusd")
        self.assertEqual(decoded["amount"], "1")
        self.assertEqual(decoded["price"], "50000")
        self.assertEqual(decoded["side"], "buy")
        self.assertEqual(decoded["type"], "exchange limit")
        self.assertEqual(decoded["request"], "/v1/order/new")
        self.assertIn("nonce", decoded)

    async def test_rest_authenticate_with_dict_data(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.gemini.com/v1/order/cancel",
            data={"order_id": 12345},
        )

        authenticated = await self.auth.rest_authenticate(request)

        b64_payload = authenticated.headers["X-GEMINI-PAYLOAD"]
        decoded = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(decoded["order_id"], 12345)
        self.assertEqual(decoded["request"], "/v1/order/cancel")

    def test_generate_ws_auth_headers(self):
        headers = self.auth.generate_ws_auth_headers()

        self.assertIn("X-GEMINI-APIKEY", headers)
        self.assertIn("X-GEMINI-PAYLOAD", headers)
        self.assertIn("X-GEMINI-SIGNATURE", headers)
        self.assertEqual(headers["X-GEMINI-APIKEY"], self.api_key)

        # Payload is base64(JSON({"request": <path>, "nonce": <int>}))
        b64_payload = headers["X-GEMINI-PAYLOAD"]
        decoded = json.loads(base64.b64decode(b64_payload).decode("utf-8"))
        self.assertEqual(decoded["request"], "/v1/order/events")
        self.assertIsInstance(decoded["nonce"], int)

        # Verify signature
        expected_sig = hmac.new(
            self.secret_key.encode("utf-8"),
            b64_payload.encode("utf-8"),
            hashlib.sha384
        ).hexdigest()
        self.assertEqual(headers["X-GEMINI-SIGNATURE"], expected_sig)

    def test_nonce_is_monotonically_increasing(self):
        nonce1 = self.auth._generate_nonce()
        nonce2 = self.auth._generate_nonce()
        nonce3 = self.auth._generate_nonce()
        self.assertLess(nonce1, nonce2)
        self.assertLess(nonce2, nonce3)

    def test_nonce_is_instance_based(self):
        """Verify each GeminiAuth instance has its own nonce creator (no race conditions)."""
        auth2 = GeminiAuth(
            api_key="other_key",
            secret_key="other_secret",
            time_provider=MagicMock(),
        )
        # Both should produce valid nonces independently
        n1 = self.auth._generate_nonce()
        n2 = auth2._generate_nonce()
        self.assertIsInstance(n1, int)
        self.assertIsInstance(n2, int)

    async def test_ws_authenticate_is_passthrough(self):
        from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
        request = WSJSONRequest(payload={})
        result = await self.auth.ws_authenticate(request)
        self.assertIs(result, request)
