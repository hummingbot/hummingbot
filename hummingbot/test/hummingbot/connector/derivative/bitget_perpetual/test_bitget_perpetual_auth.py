import asyncio
import base64
import hashlib
import hmac
import time
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.derivative.bitget_perpetual.bitget_perpetual_auth import BitgetPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class BitgetPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"
        self.passphrase = "testPassphrase"
        self._time_synchronizer_mock = MagicMock()
        self._time_synchronizer_mock.time.return_value = 1640001112.223

        self.auth = BitgetPerpetualAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            passphrase=self.passphrase,
            time_provider=self._time_synchronizer_mock)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return str(int(time.time()))

    def test_add_auth_to_rest_request(self):
        params = {"one": "1"}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url",
            throttler_limit_id="/api/endpoint",
            params=params,
            is_auth_required=True,
            headers={},
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        raw_signature = (request.headers.get("ACCESS-TIMESTAMP")
                         + request.method.value
                         + request.throttler_limit_id + "?one=1")
        expected_signature = base64.b64encode(
            hmac.new(self.secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256).digest()
        ).decode().strip()

        params = request.params

        self.assertEqual(1, len(params))
        self.assertEqual("1", params.get("one"))
        self.assertEqual(
            self._time_synchronizer_mock.time(),
            int(request.headers.get("ACCESS-TIMESTAMP")) * 1e-3)
        self.assertEqual(self.api_key, request.headers.get("ACCESS-KEY"))
        self.assertEqual(expected_signature, request.headers.get("ACCESS-SIGN"))

    def test_ws_auth_payload(self):
        payload = self.auth.get_ws_auth_payload()

        raw_signature = str(int(self._time_synchronizer_mock.time())) + "GET/user/verify"
        expected_signature = base64.b64encode(
            hmac.new(self.secret_key.encode("utf-8"), raw_signature.encode("utf-8"), hashlib.sha256).digest()
        ).decode().strip()

        self.assertEqual(1, len(payload))
        self.assertEqual(self.api_key, payload[0]["apiKey"])
        self.assertEqual(str(int(self._time_synchronizer_mock.time())), payload[0]["timestamp"])
        self.assertEqual(expected_signature, payload[0]["sign"])

    def test_no_auth_added_to_ws_request(self):
        payload = {"one": "1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)
