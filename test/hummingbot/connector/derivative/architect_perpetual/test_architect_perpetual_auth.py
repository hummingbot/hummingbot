import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class ArchitectPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret_key_for_signing"
        self.auth = ArchitectPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_auth_adds_authorization_header(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/balances",
            is_auth_required=True,
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("Authorization", request.headers)
        self.assertTrue(request.headers["Authorization"].startswith("Bearer "))
        self.assertEqual(f"Bearer {self.api_key}", request.headers["Authorization"])

    def test_auth_adds_timestamp_header(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/balances",
            is_auth_required=True,
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("X-Timestamp", request.headers)
        self.assertTrue(request.headers["X-Timestamp"].isdigit())

    def test_auth_adds_signature_header_when_secret_provided(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/place_order",
            data=json.dumps({"symbol": "BTC-USD-PERP", "side": "buy"}),
            is_auth_required=True,
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("X-Signature", request.headers)
        self.assertTrue(len(request.headers["X-Signature"]) > 0)

    def test_auth_without_secret_no_signature(self):
        auth_no_secret = ArchitectPerpetualAuth(
            api_key=self.api_key,
            api_secret=None,
        )
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/balances",
            is_auth_required=True,
        )

        self.async_run_with_timeout(auth_no_secret.rest_authenticate(request))

        self.assertIn("Authorization", request.headers)
        self.assertNotIn("X-Signature", request.headers)

    def test_generate_signature_consistency(self):
        timestamp = 1704067200000
        method = "POST"
        path = "/api/place_order"
        body = '{"symbol": "BTC-USD-PERP"}'

        sig1 = self.auth._generate_signature(timestamp, method, path, body)
        sig2 = self.auth._generate_signature(timestamp, method, path, body)

        self.assertEqual(sig1, sig2)

    def test_generate_signature_changes_with_body(self):
        timestamp = 1704067200000
        method = "POST"
        path = "/api/place_order"
        body1 = '{"symbol": "BTC-USD-PERP"}'
        body2 = '{"symbol": "ETH-USD-PERP"}'

        sig1 = self.auth._generate_signature(timestamp, method, path, body1)
        sig2 = self.auth._generate_signature(timestamp, method, path, body2)

        self.assertNotEqual(sig1, sig2)
