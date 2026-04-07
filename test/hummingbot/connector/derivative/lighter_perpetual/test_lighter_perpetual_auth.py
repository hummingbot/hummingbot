import unittest
from unittest.mock import AsyncMock

from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth


class LighterPerpetualAuthTests(unittest.IsolatedAsyncioTestCase):

    async def test_rest_auth_adds_headers(self):
        auth = LighterPerpetualAuth(
            api_key="api-key",
            api_secret="api-secret",
        )

        request = AsyncMock()
        request.headers = {}
        result = await auth.rest_authenticate(request)

        self.assertIs(request, result)
        self.assertEqual("application/json", request.headers["accept"])
        self.assertEqual("application/json", request.headers["Content-Type"])
        self.assertEqual("api-key", request.headers["X-Api-Key"])

    async def test_rest_auth_preserves_existing_headers(self):
        auth = LighterPerpetualAuth(
            api_key="api-key",
            api_secret="api-secret",
        )

        request = AsyncMock()
        request.headers = {"X-Test": "1"}

        result = await auth.rest_authenticate(request)

        self.assertIs(request, result)
        self.assertEqual("1", request.headers["X-Test"])
        self.assertEqual("api-key", request.headers["X-Api-Key"])

    async def test_ws_auth_does_not_mutate_request(self):
        auth = LighterPerpetualAuth(
            api_key="api-key",
            api_secret="api-secret",
        )

        request = AsyncMock()
        result = await auth.ws_authenticate(request)

        self.assertIs(request, result)
