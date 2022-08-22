import asyncio
import hashlib
import hmac
from copy import copy
from unittest import TestCase
from unittest.mock import MagicMock
from typing_extensions import Awaitable

from hummingbot.connector.exchange.zigzag.zigzag_auth import ZigzagAuth
from hummingbot.connector.exchange.zigzag.zigzag_web_utils import web_utils
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class ZigzagAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.chain_id = 421613
        self.wallet = "0xBdA0D584A6F4E228b3b33098951eEF22E30B6CcA"
        self.passphrase = "testPassphrase"

        # Mock time provider to 1234567890
        now = 1234567890.000
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = now

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_auth_time_provider(self):
        auth = ZigzagAuth(
            chain_id=self.chain_id,
            wallet=self.wallet,
            passphrase=self.passphrase,
            time_provider=self.mock_time_provider
        )

        self.assertEqual(auth.time_provider, self.mock_time_provider)

    def test_rest_authenticate(self):
        auth = ZigzagAuth(
            chain_id=self.chain_id,
            wallet=self.wallet,
            passphrase=self.passphrase,
            time_provider=self.mock_time_provider
        )

        url = web_utils.public_rest_url("/")
        request = RESTRequest(method=RESTMethod.GET, url=url, is_auth_required=True)
        self.async_run_with_timeout(auth.rest_authenticate(request))

    def test_ws_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = ZigzagAuth(
            chain_id=self.chain_id,
            wallet=self.wallet,
            passphrase=self.passphrase,
            time_provider=mock_time_provider
        )

        payload = {"op": "login", "args": [self.chain_id, self.wallet]}
        request = WSJSONRequest(payload=payload, is_auth_required=True)
        self.async_run_with_timeout(auth.ws_authenticate(request))

        self.assertEqual(request.payload, payload)
        self.assertTrue(request.is_auth_required)
