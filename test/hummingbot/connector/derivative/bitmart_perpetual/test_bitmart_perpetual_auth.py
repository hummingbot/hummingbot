import asyncio
import copy
import hashlib
import hmac
import unittest
from typing import Awaitable
from urllib.parse import urlencode

from hummingbot.connector.derivative.bitmart_perpetual.bitmart_perpetual_auth import BitmartPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSJSONRequest


class BitmartPerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.memo = "TEST_MEMO"

    def setUp(self) -> None:
        super().setUp()
        self.emulated_time = 1640001112.223
        self.test_params = {
            "test_param": "test_input",
            "timestamp": int(self.emulated_time * 1e3),
        }
        self.auth = BitmartPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.secret_key,
            memo=self.memo,
            time_provider=self)

    def _get_test_payload(self):
        return urlencode(dict(copy.deepcopy(self.test_params)))

    def _get_signature_from_test_payload(self):
        return hmac.new(
            self.secret_key.encode("utf-8"),
            f"{int(self.emulated_time * 1e3)}#{self.memo}#{self._get_test_payload()}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def test_generate_signature_from_payload(self):
        payload = self._get_test_payload()
        signature = self.auth.generate_signature_from_payload(payload, int(self.emulated_time * 1e3))

        self.assertEqual(signature, self._get_signature_from_test_payload())

    def test_header_for_authentication(self):
        # Validate that headers are set correctly for REST requests
        request = RESTRequest(method="POST", url="http://test-url.com", data=self._get_test_payload())
        authenticated_request = self.auth.header_for_authentication(request)

        self.assertEqual(authenticated_request["X-BM-KEY"], self.api_key)
        self.assertEqual(authenticated_request["X-BM-TIMESTAMP"], int(self.emulated_time * 1e3))
        self.assertEqual(
            authenticated_request["X-BM-SIGN"],
            self._get_signature_from_test_payload()
        )

    def test_ws_authenticate(self):
        request: WSJSONRequest = WSJSONRequest(
            payload={"TEST": "SOME_TEST_PAYLOAD"}, throttler_limit_id="TEST_LIMIT_ID", is_auth_required=True
        )

        signed_request: WSJSONRequest = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(request, signed_request)
