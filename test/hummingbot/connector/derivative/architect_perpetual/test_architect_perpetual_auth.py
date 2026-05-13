import asyncio
import json
import re
from typing import Any, Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from aioresponses import aioresponses

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class ArchitectPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"
        self.api_secret = "test_secret_key"
        self._time_synchronizer_mock = MagicMock()
        self._time_synchronizer_mock.time.return_value = 1640001112.223

        self.auth = ArchitectPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.api_secret,
            time_provider=self._time_synchronizer_mock,
            domain=CONSTANTS.SANDBOX_DOMAIN,
        )

    @staticmethod
    def async_run_with_timeout(coroutine: Awaitable, timeout: int = 1) -> Any:
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @aioresponses()
    def test_add_auth_to_rest_request(self, api_mock: aioresponses):
        expected_token = "test-token"
        url = web_utils.public_rest_url(CONSTANTS.AUTH_TOKEN_ENDPOINT, domain=CONSTANTS.SANDBOX_DOMAIN)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        api_mock.post(regex_url, body=json.dumps({"token": expected_token}))
        url = web_utils.private_rest_url(CONSTANTS.RISK_ENDPOINT, domain=CONSTANTS.SANDBOX_DOMAIN)
        api_mock.get(url, body=json.dumps({}))

        request = RESTRequest(method=RESTMethod.GET, url=CONSTANTS.RISK_ENDPOINT)
        request = self.async_run_with_timeout(self.auth.rest_authenticate(request=request))

        self.assertIn("Authorization", request.headers)
        self.assertEqual(request.headers["Authorization"], f"Bearer {expected_token}")
