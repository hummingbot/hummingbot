import asyncio
import copy
import hmac
import unittest
from typing import Awaitable
from urllib.parse import urlencode

from requests import Request

from hummingbot.connector.derivative.ftx_perpetual.ftx_perpetual_auth import FtxPerpetualAuth


class FtxPerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.subaccount_name = "TEST_SUBACCOUNT"

        cls.auth = FtxPerpetualAuth(api_key=cls.api_key, secret_key=cls.secret_key, subaccount_name=cls.subaccount_name)

        cls.test_params = {"test_param": "test_input"}
        cls.test_url = 'http://test/url'

    def setUp(self) -> None:
        super().setUp()
        self.test_params = {"test_param": "test_input"}

    def _get_test_payload(self):
        return urlencode(dict(copy.deepcopy(self.test_params)))

    def _get_signature_from_test_payload(self, method, ts, payload):
        request = Request(method, self.test_url, json=payload)
        prepared = request.prepare()
        content_to_sign = f'{ts}{prepared.method}{prepared.path_url}'.encode()
        content_to_sign += prepared.body

        return hmac.new(
            self.auth.secret_key.encode(), content_to_sign, 'sha256'
        ).hexdigest()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_generate_auth_dict(self):
        payload = self._get_test_payload()
        auth_dict = self.auth.generate_auth_dict('POST', self.test_url, body=payload)
        signature = auth_dict['FTX-SIGN']
        ts = auth_dict['FTX-TS']

        self.assertEqual(signature, self._get_signature_from_test_payload('POST', ts, payload))

    def _get_websocket_subscription_signature(self, ts):
        presign = f"{ts}websocket_login"
        sign = hmac.new(self.secret_key.encode(), presign.encode(), 'sha256').hexdigest()
        subscribe = {
            "args": {
                "key": self.api_key,
                "sign": sign,
                "time": ts,
            },
            "op": "login"
        }
        if self.subaccount_name is not None and self.subaccount_name != "":
            subscribe["args"]["subaccount"] = self.subaccount_name

        return subscribe

    def test_generate_websocket_subscription(self):
        signed_request = self.auth.generate_websocket_subscription()
        ts = signed_request['args']['time']
        request = self._get_websocket_subscription_signature(ts)
        self.assertEqual(request, signed_request)
