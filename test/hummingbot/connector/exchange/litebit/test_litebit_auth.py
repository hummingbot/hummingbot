import asyncio
import hashlib
import hmac
import json
import urllib
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.litebit.litebit_auth import LitebitAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class LitebitAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        self.auth = LitebitAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=mock_time_provider,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _sign(self, message: str, key: str) -> str:
        signed_message = hmac.new(
            key.encode(),
            message.encode(),
            hashlib.sha256).hexdigest()
        return signed_message

    def test_add_auth_headers_to_get_request_without_params(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = str(int(self.auth.time_provider.time.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["LITEBIT-API-KEY"])
        self.assertEqual(expected_timestamp, request.headers["LITEBIT-TIMESTAMP"])
        path = urllib.parse.urlsplit(request.url).path
        expected_signature = self._sign(expected_timestamp + "GET" + path, key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["LITEBIT-SIGNATURE"])

    def test_add_auth_headers_to_get_request_with_params(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            params={"param2": "value2", "param1": "value1"},
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        full_request_path = f"{urllib.parse.urlsplit(request.url).path}?{urllib.parse.urlencode(request.params)}"

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = str(int(self.auth.time_provider.time.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["LITEBIT-API-KEY"])
        self.assertEqual(expected_timestamp, request.headers["LITEBIT-TIMESTAMP"])
        expected_signature = self._sign(expected_timestamp + "GET" + full_request_path, key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["LITEBIT-SIGNATURE"])

    def test_add_auth_headers_to_post_request(self):
        body = {"param_z": "value_param_z", "param_a": "value_param_a"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://api.exchange.litebit.eu/endpoint",
            data=json.dumps(body),
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = str(int(self.auth.time_provider.time.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["LITEBIT-API-KEY"])
        self.assertEqual(expected_timestamp, request.headers["LITEBIT-TIMESTAMP"])
        path = urllib.parse.urlsplit(request.url).path
        expected_signature = self._sign(expected_timestamp + "POST" + path + json.dumps(body),
                                        key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["LITEBIT-SIGNATURE"])

    def test_no_auth_added_to_wsrequest(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)

    def test_websocket_login_parameters(self):
        self.auth.time_provider.time.return_value = 1557246346.499
        secret = "Y2QTHI23f23f23jfjas23f23To0RfUwX3H42fvN-"
        self.auth = LitebitAuth(api_key=self.api_key, secret_key=secret, time_provider=self.auth.time_provider)

        payload = self.auth.websocket_login_parameters()

        expected_timestamp = int(self.auth.time_provider.time.return_value * 1e3)
        self.assertEqual(self.api_key, payload["api_key"])
        self.assertEqual(expected_timestamp, payload["timestamp"])
        expected_signature = "bcd8c681c491d763707e5c3ff5a52a7810d2ebe600d79d7a388a14d9ca3912b7"  # noqa: mock
        self.assertEqual(expected_signature, payload["signature"])
