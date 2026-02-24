import asyncio
from unittest import TestCase

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class TestDecibelPerpetualAuth(TestCase):
    def setUp(self):
        self.token = "test_token"
        self.origin = "https://example.com/trade"
        self.auth = DecibelPerpetualAuth(bearer_token=self.token, origin=self.origin)

    def test_rest_authenticate_adds_headers(self):
        request = RESTRequest(method=RESTMethod.GET, url="https://api.mainnet.aptoslabs.com/decibel/api/v1/markets")
        result = asyncio.get_event_loop().run_until_complete(self.auth.rest_authenticate(request))
        self.assertEqual(result.headers["Origin"], self.origin)
        self.assertEqual(result.headers["Authorization"], f"Bearer {self.token}")

    def test_ws_authenticate_is_noop(self):
        req = WSJSONRequest(payload={"method": "subscribe", "topic": "all_market_prices"})
        result = asyncio.get_event_loop().run_until_complete(self.auth.ws_authenticate(req))
        self.assertIs(result, req)

    def test_ws_headers_contains_sec_websocket_protocol(self):
        self.assertEqual(self.auth.ws_headers["Sec-WebSocket-Protocol"], f"decibel, {self.token}")
