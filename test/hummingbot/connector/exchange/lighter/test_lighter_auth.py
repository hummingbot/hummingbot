import asyncio
from typing import Awaitable
from unittest import TestCase

from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class LighterAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.auth = LighterAuth(api_key="test-api-key", api_secret="test-secret", account_identifier="123")

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_rest_authenticate_injects_headers(self):
        request = RESTRequest(method=RESTMethod.GET, url="https://test.url", is_auth_required=True)
        authed_request = self.async_run_with_timeout(self.auth.rest_authenticate(request=request))

        self.assertEqual("application/json", authed_request.headers["accept"])
        self.assertEqual("application/json", authed_request.headers["Content-Type"])
        self.assertEqual("test-api-key", authed_request.headers["X-Api-Key"])

    def test_rest_authenticate_keeps_headers(self):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url",
            is_auth_required=True,
            headers={"X-Test": "1"},
        )
        authed_request = self.async_run_with_timeout(self.auth.rest_authenticate(request=request))

        self.assertEqual("1", authed_request.headers["X-Test"])
        self.assertEqual("test-api-key", authed_request.headers["X-Api-Key"])
