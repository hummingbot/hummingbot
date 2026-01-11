import asyncio
import unittest
from typing import Awaitable

from hummingbot.connector.derivative.aevo_perpetual.aevo_perpetual_auth import AevoPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class AevoPerpetualAuthUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.emulated_time = 1640001112.223
        self.auth = AevoPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.secret_key,
            time_provider=self)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def time(self):
        return self.emulated_time

    def test_rest_authenticate_adds_headers(self):
        request: RESTRequest = RESTRequest(
            method=RESTMethod.GET, url="https://api.aevo.xyz/account", is_auth_required=True
        )
        signed_request: RESTRequest = self.async_run_with_timeout(self.auth.rest_authenticate(request))
        self.assertIn("AEVO-KEY", signed_request.headers)
        self.assertEqual(signed_request.headers["AEVO-KEY"], self.api_key)

    def test_ws_authenticate_passthrough(self):
        request: WSJSONRequest = WSJSONRequest(
            payload={"TEST": "PAYLOAD"}, throttler_limit_id="TEST", is_auth_required=True
        )
        signed_request: WSJSONRequest = self.async_run_with_timeout(self.auth.ws_authenticate(request))
        self.assertEqual(request, signed_request)

    def test_get_ws_auth_payload(self):
        payload = self.auth.get_ws_auth_payload()
        self.assertEqual(payload["op"], "auth")
        self.assertIn("data", payload)
