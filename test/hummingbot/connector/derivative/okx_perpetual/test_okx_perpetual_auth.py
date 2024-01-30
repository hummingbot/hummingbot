import asyncio
import base64
import hmac
import re
from datetime import datetime
from typing import Awaitable, Optional
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth import OkxPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class OkxPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.api_secret = "testSecretKey"
        self.api_passphrase = "testPassphrase"
        self.auth = OkxPerpetualAuth(api_key=self.api_key, api_secret=self.api_secret, passphrase=self.api_passphrase)

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def _get_timestamp():
        return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'

    def generate_signature_from_payload(self, timestamp: str, method: RESTMethod, url: str, params: Optional[str] = None):
        if params is None:
            params = ''
        pattern = re.compile(r'https://www.okx.com')
        path_url = re.sub(pattern, '', url)
        raw_signature = str(timestamp) + str.upper(method.value) + path_url + str(params)
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(raw_signature, encoding='utf-8'),
                       digestmod='sha256')
        d = mac.digest()
        return str(base64.b64encode(d), encoding='utf-8')

    @patch("hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth.OkxPerpetualAuth._get_timestamp")
    def test_add_auth_to_rest_request_with_params(self, ts_mock: MagicMock):
        params = {"one": "1"}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://www.okx.com/api/endpoint",
            params=params,
            is_auth_required=True,
        )

        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_signature = self.generate_signature_from_payload(timestamp, request.method, request.url, params)

        params = request.params
        headers = request.headers

        self.assertEqual(4, len(headers))
        self.assertEqual("1", params.get("one"))
        self.assertEqual(timestamp, headers.get("OK-ACCESS-TIMESTAMP"))
        self.assertEqual(self.api_key, headers.get("OK-ACCESS-KEY"))
        self.assertEqual(self.api_passphrase, headers.get("OK-ACCESS-PASSPHRASE"))
        self.assertEqual(expected_signature, headers.get("OK-ACCESS-SIGN"))

    @patch("hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth.OkxPerpetualAuth._get_timestamp")
    def test_add_auth_to_rest_request_without_params(self, ts_mock: MagicMock):
        params = {}
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://www.okx.com/api/endpoint",
            params=params,
            is_auth_required=True,
        )

        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        raw_signature = str(timestamp) + str.upper(request.method.value) + "/api/endpoint" + str(params)
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(raw_signature, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        expected_signature = str(base64.b64encode(d), encoding='utf-8')

        params = request.params
        headers = request.headers

        self.assertEqual(4, len(headers))
        self.assertDictEqual(params, {})
        self.assertEqual(timestamp, headers.get("OK-ACCESS-TIMESTAMP"))
        self.assertEqual(self.api_key, headers.get("OK-ACCESS-KEY"))
        self.assertEqual(self.api_passphrase, headers.get("OK-ACCESS-PASSPHRASE"))
        self.assertEqual(expected_signature, headers.get("OK-ACCESS-SIGN"))

    @patch("hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth.OkxPerpetualAuth._get_timestamp")
    def test_ws_auth_args(self, ts_mock: MagicMock):
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        ws_auth_url = "/users/self/verify"

        expected_signature = self.generate_signature_from_payload(timestamp=timestamp,
                                                                  method=RESTMethod.GET,
                                                                  url=ws_auth_url)

        payload = self.auth.get_ws_auth_args()

        self.assertEqual(1, len(payload))
        self.assertEqual(4, len(payload[0]))
        self.assertEqual(self.api_key, payload[0]["apiKey"])
        self.assertEqual(self.api_passphrase, payload[0]["passphrase"])
        self.assertEqual(timestamp, payload[0]["timestamp"])
        self.assertEqual(expected_signature, payload[0]["sign"])

    def test_get_timestamp(self):
        timestamp = self.auth._get_timestamp()
        self.assertEqual(24, len(timestamp))
        self.assertEqual("Z", timestamp[-1])
        self.assertEqual("T", timestamp[10])
        self.assertEqual(":", timestamp[13])
        self.assertEqual(":", timestamp[16])
        self.assertEqual(".", timestamp[19])

    def test_ws_authenticate(self):
        mock_request = MagicMock(spec=WSRequest)

        # Call ws_authenticate with the mock_request
        result = self.async_run_with_timeout(self.auth.ws_authenticate(mock_request))

        # Assert that the returned value is the same as the mock_request
        self.assertIs(result, mock_request)
