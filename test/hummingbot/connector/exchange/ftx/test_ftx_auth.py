import asyncio
import hashlib
import hmac
import json
import urllib
from typing import Awaitable
from unittest import TestCase
from unittest.mock import patch

from hummingbot.connector.exchange.ftx.ftx_auth import FtxAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class FtxAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"
        self.subaccount_name = "test!?Subaccount"

        self.auth = FtxAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            subaccount_name=self.subaccount_name,
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

    @patch("hummingbot.connector.exchange.ftx.ftx_auth.FtxAuth._time")
    def test_add_auth_headers_to_get_request_without_params(self, time_mock):
        time_mock.return_value = 1640001112.223334

        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = str(int(time_mock.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["FTX-KEY"])
        self.assertEqual(expected_timestamp, request.headers["FTX-TS"])
        path = urllib.parse.urlsplit(request.url).path
        expected_signature = self._sign(expected_timestamp + "GET" + path, key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["FTX-SIGN"])
        self.assertEqual(urllib.parse.quote(self.subaccount_name), request.headers["FTX-SUBACCOUNT"])

    @patch("hummingbot.connector.exchange.ftx.ftx_auth.FtxAuth._time")
    def test_add_auth_headers_to_get_request_with_params(self, time_mock):
        time_mock.return_value = 1640001112.223334

        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            params={"param2": "value2", "param1": "value1"},
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        full_request_path = f"{urllib.parse.urlsplit(request.url).path}?{urllib.parse.urlencode(request.params)}"

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = str(int(time_mock.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["FTX-KEY"])
        self.assertEqual(expected_timestamp, request.headers["FTX-TS"])
        expected_signature = self._sign(expected_timestamp + "GET" + full_request_path, key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["FTX-SIGN"])
        self.assertEqual(urllib.parse.quote(self.subaccount_name), request.headers["FTX-SUBACCOUNT"])

    @patch("hummingbot.connector.exchange.ftx.ftx_auth.FtxAuth._time")
    def test_add_auth_headers_to_post_request(self, time_mock):
        body = {"param_z": "value_param_z", "param_a": "value_param_a"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/api/endpoint",
            data=json.dumps(body),
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = str(int(time_mock.return_value * 1e3))
        self.assertEqual(self.api_key, request.headers["FTX-KEY"])
        self.assertEqual(expected_timestamp, request.headers["FTX-TS"])
        path = urllib.parse.urlsplit(request.url).path
        expected_signature = self._sign(expected_timestamp + "POST" + path + json.dumps(body),
                                        key=self.secret_key)
        self.assertEqual(expected_signature, request.headers["FTX-SIGN"])
        self.assertEqual(urllib.parse.quote(self.subaccount_name), request.headers["FTX-SUBACCOUNT"])

    @patch("hummingbot.connector.exchange.ftx.ftx_auth.FtxAuth._time")
    def test_subaccount_not_included_in_auth_headers_if_not_configured_in_auth(self, time_mock):
        time_mock.return_value = 1640001112.223334
        local_auth = FtxAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )

        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            is_auth_required=True,
            throttler_limit_id="/endpoint"
        )

        self.async_run_with_timeout(local_auth.rest_authenticate(request))

        self.assertNotIn("FTX-SUBACCOUNT", request.headers)

    def test_no_auth_added_to_wsrequest(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)

    @patch("hummingbot.connector.exchange.ftx.ftx_auth.FtxAuth._time")
    def test_websocket_login_parameters(self, time_mock):
        time_mock.return_value = 1557246346.499
        secret = "Y2QTHI23f23f23jfjas23f23To0RfUwX3H42fvN-"
        self.auth = FtxAuth(api_key=self.api_key, secret_key=secret, subaccount_name=self.subaccount_name)

        payload = self.auth.websocket_login_parameters()

        expected_timestamp = int(time_mock.return_value * 1e3)
        self.assertEqual(self.api_key, payload["key"])
        self.assertEqual(expected_timestamp, payload["time"])
        expected_signature = "d10b5a67a1a941ae9463a60b285ae845cdeac1b11edc7da9977bef0228b96de9"  # noqa: mock
        self.assertEqual(expected_signature, payload["sign"])
        self.assertEqual(urllib.parse.quote(self.subaccount_name), payload["subaccount"])

    @patch("hummingbot.connector.exchange.ftx.ftx_auth.FtxAuth._time")
    def test_subaccount_not_included_in_websocket_login_parameters(self, time_mock):
        time_mock.return_value = 1557246346.499
        local_auth = FtxAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
        )
        payload = local_auth.websocket_login_parameters()

        self.assertNotIn("subaccount", payload)
