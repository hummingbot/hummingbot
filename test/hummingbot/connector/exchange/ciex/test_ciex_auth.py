import asyncio
import hashlib
import hmac
import json
import urllib
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.ciex.ciex_auth import CiexAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class CiexAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = CiexAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.mock_time_provider,
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

        expected_timestamp = str(int(self.mock_time_provider.time.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["X-CH-APIKEY"])
        self.assertEqual(expected_timestamp, request.headers["X-CH-TS"])
        path = urllib.parse.urlsplit(request.url).path
        expected_signature = self._sign(str(expected_timestamp) + request.method.name + path, key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["X-CH-SIGN"])

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

        expected_timestamp = str(int(self.mock_time_provider.time.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["X-CH-APIKEY"])
        self.assertEqual(expected_timestamp, request.headers["X-CH-TS"])
        expected_signature = self._sign(str(expected_timestamp) + request.method.name + full_request_path,
                                        key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["X-CH-SIGN"])

    def test_add_auth_headers_to_post_request(self):
        body = {"param_z": "value_param_z", "param_a": "value_param_a"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/endpoint",
            data=json.dumps(body),
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = str(int(self.mock_time_provider.time.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["X-CH-APIKEY"])
        self.assertEqual(expected_timestamp, request.headers["X-CH-TS"])
        path = urllib.parse.urlsplit(request.url).path
        expected_signature = self._sign(str(expected_timestamp) + request.method.name + path + json.dumps(body),
                                        key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["X-CH-SIGN"])

    def test_no_auth_added_to_wsrequest(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)
