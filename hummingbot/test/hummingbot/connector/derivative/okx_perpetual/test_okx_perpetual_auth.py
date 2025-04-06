import asyncio
import base64
import hashlib
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

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = OkxPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            passphrase=self.api_passphrase,
            time_provider=self.mock_time_provider,
        )

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def _get_timestamp():
        return datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'

    @staticmethod
    def _format_timestamp(timestamp: int) -> str:
        return datetime.utcfromtimestamp(timestamp).isoformat(timespec="milliseconds") + 'Z'

    @staticmethod
    def _sign(message: str, key: str) -> str:
        signed_message = base64.b64encode(
            hmac.new(
                key.encode("utf-8"),
                message.encode("utf-8"),
                hashlib.sha256).digest())
        return signed_message.decode("utf-8")

    def generate_signature_from_payload(self, timestamp: str, method: RESTMethod, url: str, body: Optional[str] = None):
        str_body = ""
        if body is not None:
            str_body = str(body).replace("'", '"')
        pattern = re.compile(r'https://www.okx.com')
        path_url = re.sub(pattern, '', url)
        raw_signature = str(timestamp) + str.upper(method.value) + path_url + str_body
        mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(raw_signature, encoding='utf-8'),
                       digestmod='sha256')
        d = mac.digest()
        return str(base64.b64encode(d), encoding='utf-8')

    @patch("hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth.OkxPerpetualAuth._get_timestamp")
    def test_add_auth_to_rest_request_with_params(self, ts_mock: MagicMock):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/endpoint",
            params={'ordId': '123', 'instId': 'BTC-USDT'},
            is_auth_required=True,
            throttler_limit_id="/api/endpoint"
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        expected_timestamp = self._format_timestamp(timestamp=1000)
        self.assertEqual(self.api_key, request.headers["OK-ACCESS-KEY"])
        self.assertEqual(expected_timestamp, request.headers["OK-ACCESS-TIMESTAMP"])
        expected_signature = self._sign(expected_timestamp + "GET" + f"{request.throttler_limit_id}?ordId=123&instId=BTC-USDT",
                                        key=self.api_secret)
        self.assertEqual(expected_signature, request.headers["OK-ACCESS-SIGN"])
        expected_passphrase = self.api_passphrase
        self.assertEqual(expected_passphrase, request.headers["OK-ACCESS-PASSPHRASE"])

    @patch("hummingbot.connector.derivative.okx_perpetual.okx_perpetual_auth.OkxPerpetualAuth._get_timestamp")
    def test_add_auth_to_rest_request_without_params(self, ts_mock: MagicMock):
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
        expected_signature = self._sign(expected_timestamp + "GET" + request.throttler_limit_id, key=self.api_secret)
        self.assertEqual(expected_signature, request.headers["OK-ACCESS-SIGN"])
        expected_passphrase = self.api_passphrase
        self.assertEqual(expected_passphrase, request.headers["OK-ACCESS-PASSPHRASE"])

    @patch("time.time")
    def test_ws_auth_args(self, ts_mock: MagicMock):
        timestamp = 1000
        ts_mock.return_value = timestamp

        ws_auth_url = "https://www.okx.com/users/self/verify"

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

    def test_get_path_from_url(self):
        url = 'https://www.okx.com/api/v5/account/balance'
        expected_path = '/api/v5/account/balance'
        result = self.auth.get_path_from_url(url)
        self.assertEqual(result, expected_path)

    def test_get_path_from_url_no_match(self):
        url = 'https://example.com/api/v1/users'
        expected_path = 'https://example.com/api/v1/users'
        result = self.auth.get_path_from_url(url)
        self.assertEqual(result, expected_path)
