import hashlib
import hmac
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.xt.xt_auth import (
    XtAuth,
    build_auth_headers,
    build_signature_payload,
    canonical_query_string,
    compact_json_payload,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class XtAuthTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = MagicMock()
        self.clock.time.return_value = 1700000000.123
        self.auth = XtAuth("test-key", "test-secret", self.clock)

    async def test_get_signs_sorted_query_and_preserves_headers(self):
        request = RESTRequest(
            method=RESTMethod.GET, url="https://sapi.xt.com/v4/order",
            params={"symbol": "btc_usdt", "clientOrderId": "HBOT1234"},
            headers={"X-Test": "retained"}, is_auth_required=True,
        )
        await self.auth.rest_authenticate(request)
        payload = ("validate-algorithms=HmacSHA256&validate-appkey=test-key&validate-recvwindow=5000"
                   "&validate-timestamp=1700000000123#GET#/v4/order#clientOrderId=HBOT1234&symbol=btc_usdt")
        expected = hmac.new(b"test-secret", payload.encode(), hashlib.sha256).hexdigest()
        self.assertEqual(expected, request.headers["validate-signature"])
        self.assertEqual(["clientOrderId", "symbol"], list(request.params))
        self.assertEqual("retained", request.headers["X-Test"])

    async def test_post_signs_the_compact_body_sent_on_wire(self):
        request = RESTRequest(method=RESTMethod.POST, url="https://sapi.xt.com/v4/order",
                              data='{"symbol": "btc_usdt", "price": "65000.00"}', is_auth_required=True)
        await self.auth.rest_authenticate(request)
        payload = ("validate-algorithms=HmacSHA256&validate-appkey=test-key&validate-recvwindow=5000"
                   '&validate-timestamp=1700000000123#POST#/v4/order#{"symbol":"btc_usdt","price":"65000.00"}')
        self.assertEqual(hmac.new(b"test-secret", payload.encode(), hashlib.sha256).hexdigest(),
                         request.headers["validate-signature"])
        self.assertEqual('{"symbol":"btc_usdt","price":"65000.00"}', request.data)
        self.assertEqual("application/json", request.headers["Content-Type"])

    async def test_delete_with_no_body_and_custom_window(self):
        self.auth.recv_window_ms = 60000
        request = RESTRequest(method=RESTMethod.DELETE, url="https://sapi.xt.com/v4/order/1234")
        await self.auth.rest_authenticate(request)
        self.assertEqual("60000", request.headers["validate-recvwindow"])
        self.assertIsNone(request.data)

    async def test_websocket_auth_is_passthrough(self):
        request = WSJSONRequest(payload={"method": "subscribe"})
        self.assertIs(request, await self.auth.ws_authenticate(request))

    def test_canonical_query_escapes_and_expands_sequences(self):
        self.assertEqual("a=hello+world&z=1&z=2", canonical_query_string({"z": [1, 2], "a": "hello world"}))
        self.assertEqual("", canonical_query_string(None))

    def test_compact_json_accepts_payload_shapes(self):
        for value in (None, ""):
            self.assertEqual("", compact_json_payload(value))
        self.assertEqual('{"a":1}', compact_json_payload({"a": 1}))
        self.assertEqual('{"a":1}', compact_json_payload('{"a": 1}'))
        self.assertEqual("invalid-json", compact_json_payload("invalid-json"))

    def test_signature_payload_includes_query_and_body(self):
        headers = {"validate-algorithms": "HmacSHA256", "validate-appkey": "key",
                   "validate-recvwindow": "5000", "validate-timestamp": "123"}
        self.assertTrue(build_signature_payload(headers, "post", "/v4/order", {"z": 1}, {"a": 2})
                        .endswith('#POST#/v4/order#z=1#{"a":2}'))
        result = build_auth_headers("key", "secret", 123, "GET", "/v4/balances")
        self.assertEqual("123", result["validate-timestamp"])
        self.assertEqual(64, len(result["validate-signature"]))
