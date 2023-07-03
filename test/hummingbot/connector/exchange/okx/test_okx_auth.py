import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.okx.okx_auth import OkxAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class OkxAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.passphrase = "testPassphrase"
        self.secret_key = "testSecretKey"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = OkxAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            passphrase=self.passphrase,
            time_provider=self.mock_time_provider,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _sign(self, message: str, key: str) -> str:
        signed_message = base64.b64encode(
            hmac.new(
                key.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256).digest())
        return signed_message.decode("utf-8")

    def _format_timestamp(self, timestamp: int) -> str:
        return datetime.utcfromtimestamp(timestamp).isoformat(timespec="milliseconds") + 'Z'

    def test_add_auth_headers_to_get_request_without_params(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = self._format_timestamp(timestamp=1000)
        self.assertEqual(self.api_key, request.headers["OK-ACCESS-KEY"])
        self.assertEqual(expected_timestamp, request.headers["OK-ACCESS-TIMESTAMP"])
        expected_signature = self._sign(expected_timestamp + "GET" + request.throttler_limit_id, key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["OK-ACCESS-SIGN"])
        expected_passphrase = self.passphrase
        self.assertEqual(expected_passphrase, request.headers["OK-ACCESS-PASSPHRASE"])

    def test_add_auth_headers_to_get_request_with_params(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            params = {'ordId': '123', 'instId': 'BTC-USDT'},
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = self._format_timestamp(timestamp=1000)
        self.assertEqual(self.api_key, request.headers["OK-ACCESS-KEY"])
        self.assertEqual(expected_timestamp, request.headers["OK-ACCESS-TIMESTAMP"])
        expected_signature = self._sign(expected_timestamp + "GET" + f"{request.throttler_limit_id}?ordId=123&instId=BTC-USDT", key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["OK-ACCESS-SIGN"])
        expected_passphrase = self.passphrase
        self.assertEqual(expected_passphrase, request.headers["OK-ACCESS-PASSPHRASE"])

    def test_add_auth_headers_to_post_request(self):
        body = {"param_z": "value_param_z", "param_a": "value_param_a"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/endpoint",
            data=json.dumps(body),
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = self._format_timestamp(timestamp=1000)
        self.assertEqual(self.api_key, request.headers["OK-ACCESS-KEY"])
        self.assertEqual(expected_timestamp, request.headers["OK-ACCESS-TIMESTAMP"])
        expected_signature = self._sign(expected_timestamp + "POST" + request.throttler_limit_id + json.dumps(body),
                                        key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["OK-ACCESS-SIGN"])
        expected_passphrase = self.passphrase
        self.assertEqual(expected_passphrase, request.headers["OK-ACCESS-PASSPHRASE"])

    def test_no_auth_added_to_wsrequest(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)
