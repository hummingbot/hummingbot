import hashlib
import hmac
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.kalqix import kalqix_auth as auth_module
from hummingbot.connector.exchange.kalqix.kalqix_auth import KalqixAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class KalqixAuthTests(IsolatedAsyncioWrapperTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.api_secret = "testApiSecret"
        self.agent_index = 6
        # Valid 32-byte BIP-340 private key (in range 1..n-1).
        self.agent_private_key = "0000000000000000000000000000000000000000000000000000000000000003"
        self.fixed_time_seconds = 1234567890.0

        self.time_provider = MagicMock()
        self.time_provider.time.return_value = self.fixed_time_seconds

        self.auth = KalqixAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            agent_index=self.agent_index,
            agent_private_key=self.agent_private_key,
            time_provider=self.time_provider,
        )

    def _expected_signature(self, method: str, path: str, query: str, body: str, timestamp: int) -> str:
        signing_string = f"{method}|{path}|{query}|{body}|{timestamp}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            signing_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    async def test_rest_authenticate_sets_three_headers_and_signature(self):
        body_payload = {"side": "BUY", "agent_index": self.agent_index, "ticker": "BTC/USDC"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.kalqix.com/v1/orders",
            data=json.dumps(body_payload),
            is_auth_required=True,
        )

        configured_request = await self.auth.rest_authenticate(request)

        expected_timestamp = int(self.fixed_time_seconds * 1e3)
        expected_body = json.dumps(body_payload, sort_keys=True, separators=(",", ":"))
        expected_signature = self._expected_signature(
            method="POST", path="/v1/orders", query="", body=expected_body, timestamp=expected_timestamp,
        )

        self.assertEqual(self.api_key, configured_request.headers["x-api-key"])
        self.assertEqual(str(expected_timestamp), configured_request.headers["x-api-timestamp"])
        self.assertEqual(expected_signature, configured_request.headers["x-api-signature"])

    async def test_rest_authenticate_rewrites_body_to_canonical_form(self):
        body_payload = {"side": "BUY", "agent_index": self.agent_index, "ticker": "BTC/USDC"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.kalqix.com/v1/orders",
            data=json.dumps(body_payload),
            is_auth_required=True,
        )

        configured_request = await self.auth.rest_authenticate(request)

        self.assertEqual(
            json.dumps(body_payload, sort_keys=True, separators=(",", ":")),
            configured_request.data,
        )

    async def test_rest_authenticate_signs_sorted_query(self):
        params = {"timestamp": 1234567890000, "agent_index": self.agent_index, "signature": "deadbeef"}
        request = RESTRequest(
            method=RESTMethod.DELETE,
            url="https://api.kalqix.com/v1/orders/the-order-id",
            params=params,
            is_auth_required=True,
        )

        configured_request = await self.auth.rest_authenticate(request)

        expected_timestamp = int(self.fixed_time_seconds * 1e3)
        expected_query = "agent_index=6&signature=deadbeef&timestamp=1234567890000"
        expected_signature = self._expected_signature(
            method="DELETE",
            path="/v1/orders/the-order-id",
            query=expected_query,
            body="",
            timestamp=expected_timestamp,
        )
        self.assertEqual(expected_signature, configured_request.headers["x-api-signature"])

    def test_canonical_query_sorts_and_handles_empty(self):
        self.assertEqual("", KalqixAuth._canonical_query(None))
        self.assertEqual("", KalqixAuth._canonical_query({}))
        self.assertEqual(
            "a=1&b=2&c=3",
            KalqixAuth._canonical_query({"c": 3, "a": 1, "b": 2}),
        )

    def test_header_for_authentication_returns_three_keys(self):
        headers = self.auth.header_for_authentication(signature="abc", timestamp=999)
        self.assertEqual({"x-api-key": self.api_key, "x-api-signature": "abc", "x-api-timestamp": "999"}, headers)

    def test_sign_payload_returns_128_lowercase_hex_chars(self):
        signature = self.auth.sign_payload({"action": "PLACE_ORDER", "agent_index": self.agent_index})
        self.assertEqual(128, len(signature))
        # valid hex, lowercase
        int(signature, 16)
        self.assertEqual(signature.lower(), signature)

    def test_sign_payload_is_deterministic_with_fixed_aux_randomness(self):
        payload = {"action": "PLACE_ORDER", "agent_index": self.agent_index, "ticker": "BTC/USDC"}
        with patch.object(auth_module.os, "urandom", return_value=b"\x01" * 32):
            first_signature = self.auth.sign_payload(payload)
            second_signature = self.auth.sign_payload(payload)
        self.assertEqual(first_signature, second_signature)

    def test_sign_payload_changes_with_payload(self):
        with patch.object(auth_module.os, "urandom", return_value=b"\x01" * 32):
            signature_a = self.auth.sign_payload({"action": "PLACE_ORDER"})
            signature_b = self.auth.sign_payload({"action": "CANCEL_ORDER"})
        self.assertNotEqual(signature_a, signature_b)

    async def test_ws_authenticate_is_pass_through(self):
        request = MagicMock()
        self.assertEqual(request, await self.auth.ws_authenticate(request))
