import asyncio
import hashlib
import hmac
import time
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_auth import GateIoPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class GateIoPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"

        self.auth = GateIoPerpetualAuth(api_key=self.api_key, secret_key=self.secret_key)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return str(int(time.time() * 1e3))

    def _get_expiration_timestamp(self):
        return str(int(time.time() + 1 * 1e3))

    @patch(
        "hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_auth.GateIoPerpetualAuth._get_timestamp")
    def test_add_auth_to_rest_request(self, ts_mock: MagicMock):
        params = {"one": "1"}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/v4/futures/orders",
            params=params,
            is_auth_required=True,
        )
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        m = hashlib.sha512()
        body_hash = m.hexdigest()

        # raw_signature = "api_key=" + self.api_key + "&one=1" + "&timestamp=" + timestamp
        raw_signature = f'GET\n/api/v4/futures/orders\none=1\n{body_hash}\n{timestamp}'
        expected_signature = hmac.new(self.secret_key.encode("utf-8"),
                                      raw_signature.encode("utf-8"),
                                      hashlib.sha512).hexdigest()
        params = request.params
        headers = request.headers

        self.assertEqual(1, len(params))
        self.assertEqual("1", params.get("one"))
        self.assertEqual(self.api_key, headers.get("KEY"))
        self.assertEqual(expected_signature, headers.get("SIGN"))

    def test_no_auth_added_to_ws_request(self):
        payload = {
            "time": 1611541000,
            "channel": 1,
            "event": "subscribe",
            "error": None,
            "result": {
                "status": "success"
            }
        }
        request = WSJSONRequest(payload=payload, is_auth_required=False)
        self.assertNotIn("auth", request.payload)

    def test_ws_authenticate(self):
        request: WSJSONRequest = WSJSONRequest(
            payload={
                "time": 1611541000,
                "channel": 1,
                "event": "subscribe",
                "error": None,
                "result": {
                    "status": "success"
                }
            }, is_auth_required=True
        )

        signed_request: WSJSONRequest = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(request, signed_request)
