import asyncio
import hashlib
import hmac
import time
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth import BybitPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class BybitPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"
        self.auth = BybitPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return str(int(time.time() * 1e3))

    def _get_expiration_timestamp(self):
        return str(int(time.time() + 1 * 1e3))

    @patch("hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth.BybitPerpetualAuth._get_timestamp")
    def test_add_auth_to_rest_request(self, ts_mock: MagicMock):
        params = {"one": "1"}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            params=params,
            is_auth_required=True,
        )
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        raw_signature = "api_key=" + self.api_key + "&one=1" + "&timestamp=" + timestamp
        expected_signature = hmac.new(self.secret_key.encode("utf-8"),
                                      raw_signature.encode("utf-8"),
                                      hashlib.sha256).hexdigest()
        params = request.params

        self.assertEqual(4, len(params))
        self.assertEqual("1", params.get("one"))
        self.assertEqual(timestamp, params.get("timestamp"))
        self.assertEqual(self.api_key, params.get("api_key"))
        self.assertEqual(expected_signature, params.get("sign"))

    @patch(
        "hummingbot.connector.derivative.bybit_perpetual.bybit_perpetual_auth"
        ".BybitPerpetualAuth._get_expiration_timestamp"
    )
    def test_ws_auth_payload(self, ts_mock: MagicMock):
        expires = self._get_expiration_timestamp()
        ts_mock.return_value = expires
        payload = self.auth.get_ws_auth_payload()

        raw_signature = "GET/realtime" + expires
        expected_signature = hmac.new(self.secret_key.encode("utf-8"),
                                      raw_signature.encode("utf-8"),
                                      hashlib.sha256).hexdigest()

        self.assertEqual(3, len(payload))
        self.assertEqual(self.api_key, payload[0])
        self.assertEqual(expires, payload[1])
        self.assertEqual(expected_signature, payload[2])

    def test_no_auth_added_to_ws_request(self):
        payload = {"one": "1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)
