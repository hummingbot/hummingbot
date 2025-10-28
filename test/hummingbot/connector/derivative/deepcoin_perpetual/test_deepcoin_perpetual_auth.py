import asyncio
import base64
import datetime
import hashlib
import hmac
import json
from time import timezone
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.derivative.deepcoin_perpetual.deepcoin_perpetual_auth import DeepcoinPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class DeepcoinPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "testSecretKey"
        self.passphrase = "testPassphrase"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = DeepcoinPerpetualAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            passphrase=self.passphrase,
            time_provider=self.mock_time_provider,
        )

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @staticmethod
    def _get_timestamp():
        ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        return ts.replace("+00:00", "Z")

    @staticmethod
    def _sign(message: str, key: str) -> str:
        # print('msg:',message,'key:',key)
        signed_message = base64.b64encode(
            hmac.new(key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
        )
        return signed_message.decode()

    # def generate_signature_from_payload(self, timestamp: str, method: RESTMethod, url: str, body: Optional[str] = None):
    #     str_body = ""
    #     if body is not None:
    #         str_body = str(body).replace("'", '"')
    #     pattern = re.compile(r'https://api.deepcoin.com')
    #     path_url = re.sub(pattern, '', url)
    #     raw_signature = str(timestamp) + str.upper(method.value) + path_url + str_body
    #     mac = hmac.new(bytes(self.api_secret, encoding='utf8'), bytes(raw_signature, encoding='utf-8'),
    #                    digestmod='sha256')
    #     d = mac.digest()
    #     return str(base64.b64encode(d), encoding='utf-8')

    def test_add_auth_to_rest_request_with_params(self):
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/deepcoin/endpoint",
            is_auth_required=True,
            throttler_limit_id="/deepcoin/endpoint",
        )
        request.data = json.dumps({"listenkey": "f24739a259bc1ac714dad2ac6690c816"})
        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        print(request.headers, request.method.value.upper(), request.throttler_limit_id, request.data)

        self.assertEqual(self.api_key, request.headers["DC-ACCESS-KEY"])
        expected_signature = self._sign(
            request.headers["DC-ACCESS-TIMESTAMP"] + "POST" + request.throttler_limit_id + request.data,
            key=self.secret_key,
        )
        self.assertEqual(expected_signature, request.headers["DC-ACCESS-SIGN"])
        expected_passphrase = self.passphrase
        self.assertEqual(expected_passphrase, request.headers["DC-ACCESS-PASSPHRASE"])

    def test_add_auth_to_rest_request_without_params(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            endpoint_url="https://test.url/deepcoin/endpoint",
            url="https://test.url/deepcoin/endpoint",
            is_auth_required=True,
            throttler_limit_id="/deepcoin/endpoint",
        )

        self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual(self.api_key, request.headers["DC-ACCESS-KEY"])
        expected_signature = self._sign(
            request.headers["DC-ACCESS-TIMESTAMP"] + "GET" + request.throttler_limit_id, key=self.secret_key
        )
        self.assertEqual(expected_signature, request.headers["DC-ACCESS-SIGN"])
        expected_passphrase = self.passphrase
        self.assertEqual(expected_passphrase, request.headers["DC-ACCESS-PASSPHRASE"])

    def test_get_timestamp(self):
        timestamp = self.auth._get_timestamp()
        # Valid timestamp 2025-02-12T22:11:59.448Z
        self.assertEqual(24, len(timestamp))
        self.assertEqual("Z", timestamp[-1])
        self.assertEqual("T", timestamp[10])
        self.assertEqual(":", timestamp[13])
        self.assertEqual(":", timestamp[16])
        self.assertEqual(".", timestamp[19])
