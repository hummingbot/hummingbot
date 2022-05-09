import asyncio
import copy
import hashlib
import hmac
import json
import unittest
from typing import Awaitable
from urllib.parse import urlencode

from mock import patch

from hummingbot.connector.derivative.bitmex_perpetual.bitmex_perpetual_auth import EXPIRATION, BitmexPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest

MOCK_TS = 1648733370.792768


class BitmexPerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.test_params = {
            "test_param": "test_input"
        }
        self.auth = BitmexPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.secret_key
        )

    def _get_test_payload(self):
        return urlencode(dict(copy.deepcopy(self.test_params)))

    def _get_signature_from_test_payload(self, payload):
        return hmac.new(
            bytes(self.auth._api_secret.encode("utf-8")),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_generate_signature_from_payload(self):
        payload = self._get_test_payload()
        signature = self.auth.generate_signature_from_payload(payload)

        self.assertEqual(signature, self._get_signature_from_test_payload(payload))

    @patch("time.time")
    def test_rest_authenticate_no_parameters_provided(self, mock_ts):
        mock_ts.return_value = MOCK_TS
        mock_path = "/TEST_PATH_URL"
        payload = 'GET' + mock_path + str(int(MOCK_TS) + EXPIRATION)
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET, url=mock_path, is_auth_required=True
        )
        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("api-key", signed_request.headers)
        self.assertEqual(signed_request.headers["api-key"], self.api_key)
        self.assertIn("api-signature", signed_request.headers)
        self.assertEqual(signed_request.headers["api-signature"], self._get_signature_from_test_payload(payload))

    @patch("time.time")
    def test_rest_authenticate_parameters_provided(self, mock_ts):
        mock_ts.return_value = MOCK_TS
        mock_path = "/TEST_PATH_URL"
        mock_query = "?test_param=param"
        payload = 'GET' + mock_path + mock_query + str(int(MOCK_TS) + EXPIRATION)
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET, url=mock_path, params={"test_param": "param"}, is_auth_required=True
        )
        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("api-key", signed_request.headers)
        self.assertEqual(signed_request.headers["api-key"], self.api_key)
        self.assertIn("api-signature", signed_request.headers)
        self.assertEqual(signed_request.headers["api-signature"], self._get_signature_from_test_payload(payload))

    @patch("time.time")
    def test_rest_authenticate_data_provided(self, mock_ts):
        mock_ts.return_value = MOCK_TS
        mock_path = "/TEST_PATH_URL"
        mock_data = json.dumps(self.test_params)
        payload = 'POST' + mock_path + str(int(MOCK_TS) + EXPIRATION) + mock_data
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST, url="/TEST_PATH_URL", data=self.test_params, is_auth_required=True
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("api-key", signed_request.headers)
        self.assertEqual(signed_request.headers["api-key"], self.api_key)
        self.assertIn("api-signature", signed_request.headers)
        self.assertEqual(signed_request.headers["api-signature"], self._get_signature_from_test_payload(payload))

    def test_generate_ws_signature(self):
        payload = 'GET/realtime' + str(int(MOCK_TS))

        signature = self.async_run_with_timeout(self.auth.generate_ws_signature(str(int(MOCK_TS))))
        self.assertEqual(signature, self._get_signature_from_test_payload(payload))
