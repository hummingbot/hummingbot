import asyncio
import copy
import hashlib
import hmac
import unittest

from typing import Awaitable
from urllib.parse import urlencode

from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class BinancePerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"

        cls.auth = BinancePerpetualAuth(api_key=cls.api_key, api_secret=cls.secret_key)

        cls.test_params = {"test_param": "test_input"}

    def setUp(self) -> None:
        super().setUp()
        self.test_params = {"test_param": "test_input"}

    def _get_test_payload(self):
        return urlencode(dict(copy.deepcopy(self.test_params)))

    def _get_signature_from_test_payload(self):
        return hmac.new(
            bytes(self.auth._api_secret.encode("utf-8")), self._get_test_payload().encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_generate_signature_from_payload(self):
        payload = self._get_test_payload()
        signature = self.auth.generate_signature_from_payload(payload)

        self.assertEqual(signature, self._get_signature_from_test_payload())

    def test_rest_authenticate_no_parameters_provided(self):
        request: RESTRequest = RESTRequest(method=RESTMethod.GET, url="/TEST_PATH_URL", is_auth_required=True)

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("X-MBX-APIKEY", signed_request.headers)
        self.assertEqual(signed_request.headers["X-MBX-APIKEY"], self.api_key)
        self.assertIsNone(signed_request.params)
        self.assertIsNone(signed_request.data)

    def test_rest_authenticate_parameters_provided(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET, url="/TEST_PATH_URL", params=copy.deepcopy(self.test_params), is_auth_required=True
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("X-MBX-APIKEY", signed_request.headers)
        self.assertEqual(signed_request.headers["X-MBX-APIKEY"], self.api_key)
        self.assertIn("signature", signed_request.params)
        self.assertEqual(signed_request.params["signature"], self._get_signature_from_test_payload())

    def test_rest_authenticate_data_provided(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST, url="/TEST_PATH_URL", data=copy.deepcopy(self.test_params), is_auth_required=True
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("X-MBX-APIKEY", signed_request.headers)
        self.assertEqual(signed_request.headers["X-MBX-APIKEY"], self.api_key)
        self.assertIn("signature", signed_request.data)
        self.assertEqual(signed_request.data["signature"], self._get_signature_from_test_payload())

    def test_ws_authenticate(self):
        request: WSRequest = WSRequest(
            payload={"TEST": "SOME_TEST_PAYLOAD"}, throttler_limit_id="TEST_LIMIT_ID", is_auth_required=True
        )

        signed_request: WSRequest = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(request, signed_request)
