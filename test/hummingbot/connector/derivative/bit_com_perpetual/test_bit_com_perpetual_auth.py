import asyncio
import hashlib
import hmac
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_auth import BitComPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class BitComPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        self.auth = BitComPerpetualAuth(api_key=self.api_key, api_secret=self.secret_key)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return 1678974447.926

    @patch(
        "hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_auth.BitComPerpetualAuth._get_timestamp")
    def test_add_auth_to_get_request(self, ts_mock: MagicMock):
        params = {"one": "1"}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/linear/v1/orders",
            params=params,
            is_auth_required=True,
        )
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        raw_signature = f'/linear/v1/orders&one=1&timestamp={int(self._get_timestamp() * 1e3)}'
        expected_signature = hmac.new(bytes(self.secret_key.encode("utf-8")),
                                      raw_signature.encode("utf-8"),
                                      hashlib.sha256).hexdigest()
        params = request.params
        headers = request.headers

        self.assertEqual(3, len(params))
        self.assertEqual("1", params.get("one"))
        self.assertEqual(self.api_key, headers.get("X-Bit-Access-Key"))
        self.assertEqual(expected_signature, params.get("signature"))

    @patch(
        "hummingbot.connector.derivative.bit_com_perpetual.bit_com_perpetual_auth.BitComPerpetualAuth._get_timestamp")
    def test_add_auth_to_post_request(self, ts_mock: MagicMock):
        params = {"one": "1"}
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/linear/v1/orders",
            data=json.dumps(params),
            is_auth_required=True,
        )
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        raw_signature = f'/linear/v1/orders&one=1&timestamp={int(self._get_timestamp() * 1e3)}'
        expected_signature = hmac.new(bytes(self.secret_key.encode("utf-8")),
                                      raw_signature.encode("utf-8"),
                                      hashlib.sha256).hexdigest()
        params = json.loads(request.data)
        headers = request.headers

        self.assertEqual(3, len(params))
        self.assertEqual("1", params.get("one"))
        self.assertEqual(self.api_key, headers.get("X-Bit-Access-Key"))
        self.assertEqual(expected_signature, params.get("signature"))
