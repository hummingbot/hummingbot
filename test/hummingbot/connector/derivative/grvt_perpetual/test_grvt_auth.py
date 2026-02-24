import asyncio
import json
from unittest import TestCase

from hummingbot.connector.derivative.grvt_perpetual.grvt_auth import GrvtAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class GrvtAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.auth = GrvtAuth(
            api_key="api_key",
            api_secret="api_secret",
            ethereum_private_key="13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930",
            account_address="0x1111111111111111111111111111111111111111",
            time_provider=lambda: 1700000000.0,
        )

    def test_rest_authenticate_adds_headers(self):
        req = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.grvt.io/v1/account",
            is_auth_required=True,
        )
        out = asyncio.run(self.auth.rest_authenticate(req))
        self.assertIn("X-GRVT-API-KEY", out.headers)
        self.assertIn("X-GRVT-TIMESTAMP", out.headers)
        self.assertIn("X-GRVT-SIGN", out.headers)

    def test_rest_authenticate_decorates_order_payload(self):
        req = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.grvt.io/v1/order",
            data=json.dumps({"type": "order", "market": "BTC-USDC", "size": "1"}),
            is_auth_required=True,
        )
        out = asyncio.run(self.auth.rest_authenticate(req))
        payload = json.loads(out.data)
        self.assertEqual("order", payload["type"])
        self.assertIn("signature", payload)
        self.assertIn("nonce", payload)

    def test_ws_authenticate_adds_auth_payload(self):
        req = WSJSONRequest(payload={"method": "subscribe"})
        out = asyncio.run(self.auth.ws_authenticate(req))
        self.assertEqual("auth", out.payload["op"])
        self.assertIn("signature", out.payload["args"])
