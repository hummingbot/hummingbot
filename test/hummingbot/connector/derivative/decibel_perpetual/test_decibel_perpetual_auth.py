import asyncio
import unittest
from unittest.mock import MagicMock

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class TestDecibelPerpetualAuth(unittest.TestCase):
    def setUp(self):
        self.api_key = "test_api_key_12345"
        self.account_address = "0xabc123def456"
        self.subaccount_address = "0xsub123account456"
        self.private_key = "0xprivate_key_hex_string"
        self.auth = DecibelPerpetualAuth(
            api_key=self.api_key,
            account_address=self.account_address,
            subaccount_address=self.subaccount_address,
            private_key=self.private_key,
        )

    def test_properties(self):
        self.assertEqual(self.auth.api_key, self.api_key)
        self.assertEqual(self.auth.account_address, self.account_address)
        self.assertEqual(self.auth.subaccount_address, self.subaccount_address)
        self.assertEqual(self.auth.private_key, self.private_key)

    def test_rest_authenticate_adds_bearer_token(self):
        loop = asyncio.get_event_loop()
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.mainnet.aptoslabs.com/decibel/api/v1/markets",
        )
        authenticated_request = loop.run_until_complete(self.auth.rest_authenticate(request))
        self.assertIn("Authorization", authenticated_request.headers)
        self.assertEqual(authenticated_request.headers["Authorization"], f"Bearer {self.api_key}")

    def test_rest_authenticate_adds_origin_header(self):
        loop = asyncio.get_event_loop()
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.mainnet.aptoslabs.com/decibel/api/v1/markets",
        )
        authenticated_request = loop.run_until_complete(self.auth.rest_authenticate(request))
        self.assertIn("Origin", authenticated_request.headers)
        self.assertEqual(
            authenticated_request.headers["Origin"],
            "https://netna-app.decibel.trade/trade",
        )

    def test_rest_authenticate_preserves_existing_headers(self):
        loop = asyncio.get_event_loop()
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.mainnet.aptoslabs.com/decibel/api/v1/markets",
            headers={"Custom-Header": "custom_value"},
        )
        authenticated_request = loop.run_until_complete(self.auth.rest_authenticate(request))
        self.assertEqual(authenticated_request.headers["Custom-Header"], "custom_value")
        self.assertIn("Authorization", authenticated_request.headers)

    def test_ws_authenticate_passthrough(self):
        loop = asyncio.get_event_loop()
        request = WSRequest(payload={})
        result = loop.run_until_complete(self.auth.ws_authenticate(request))
        self.assertEqual(result, request)

    def test_get_ws_protocols(self):
        protocols = self.auth.get_ws_protocols()
        self.assertEqual(protocols, ["decibel", self.api_key])

    def test_rest_authenticate_initializes_headers_if_none(self):
        loop = asyncio.get_event_loop()
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://api.mainnet.aptoslabs.com/decibel/api/v1/markets",
        )
        request.headers = None
        authenticated_request = loop.run_until_complete(self.auth.rest_authenticate(request))
        self.assertIsNotNone(authenticated_request.headers)
        self.assertIn("Authorization", authenticated_request.headers)


if __name__ == "__main__":
    unittest.main()
