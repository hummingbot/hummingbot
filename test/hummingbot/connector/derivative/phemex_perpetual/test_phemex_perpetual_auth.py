import asyncio
import copy
import hashlib
import hmac
import json
import unittest
from typing import Awaitable
from urllib.parse import urlencode

import hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_auth import PhemexPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class PhemexPerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.emulated_time = 1640001112.223
        self.path = "/TEST_PATH_URL"
        self.test_params = {
            "test_param": "test_input",
            "timestamp": int(self.emulated_time),
        }
        self.auth = PhemexPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.secret_key,
            time_provider=self)

    def _get_test_payload(self, is_get: bool = True):
        payload = ""
        if is_get is True:
            payload += (
                self.path
                + urlencode(dict(copy.deepcopy(self.test_params)))
                + str(int(self.emulated_time) + CONSTANTS.ONE_MINUTE))
        else:
            payload += (
                self.path
                + str(int(self.emulated_time) + CONSTANTS.ONE_MINUTE)
                + json.dumps(copy.deepcopy(self.test_params))
            )
        return payload

    def _get_signature_from_test_payload(self, is_get: bool = True):
        return hmac.new(
            bytes(self.auth._api_secret.encode("utf-8")), self._get_test_payload(is_get=is_get).encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def test_generate_signature_from_payload(self):
        payload = self._get_test_payload()
        signature = self.auth.generate_signature_from_payload(payload)

        self.assertEqual(signature, self._get_signature_from_test_payload())

    def test_rest_authenticate_parameters_provided(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET, url=self.path, params=copy.deepcopy(self.test_params), is_auth_required=True
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("x-phemex-access-token", signed_request.headers)
        self.assertEqual(signed_request.headers["x-phemex-access-token"], self.api_key)
        self.assertIn("x-phemex-request-signature", signed_request.headers)
        self.assertEqual(signed_request.headers["x-phemex-request-signature"], self._get_signature_from_test_payload())

    def test_rest_authenticate_data_provided(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.POST, url=self.path, data=json.dumps(self.test_params), is_auth_required=True
        )

        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertIn("x-phemex-access-token", signed_request.headers)
        self.assertEqual(signed_request.headers["x-phemex-access-token"], self.api_key)
        self.assertIn("x-phemex-request-signature", signed_request.headers)
        self.assertEqual(
            signed_request.headers["x-phemex-request-signature"],
            self._get_signature_from_test_payload(is_get=False)
        )

    def test_ws_authenticate(self):
        request: WSJSONRequest = WSJSONRequest(
            payload={"TEST": "SOME_TEST_PAYLOAD"}, throttler_limit_id="TEST_LIMIT_ID", is_auth_required=True
        )

        signed_request: WSJSONRequest = self.async_run_with_timeout(self.auth.ws_authenticate(request))

        self.assertEqual(request, signed_request)

    def test_get_ws_auth_payload(self):
        auth_payload = self.auth.get_ws_auth_payload()
        payload = f"{self.api_key}{int(self.emulated_time) + 2}"
        signature = hmac.new(self.secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        target_auth_payload = {
            "method": "user.auth",
            "params": [
                "API",
                self.api_key,
                signature,
                int(self.emulated_time) + 2,
            ],
            "id": 0,
        }

        self.assertEqual(target_auth_payload, auth_payload)
