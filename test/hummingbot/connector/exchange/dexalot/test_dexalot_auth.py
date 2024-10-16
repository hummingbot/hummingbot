import asyncio
from unittest import TestCase
from unittest.mock import MagicMock

from eth_account import Account
from eth_account.messages import encode_defunct
from typing_extensions import Awaitable

from hummingbot.connector.exchange.dexalot.dexalot_auth import DexalotAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class DexalotAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.wallet = Account.from_key(self._secret)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = DexalotAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, params={}, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        message = encode_defunct(text="dexalot")
        signed_message = self.wallet.sign_message(signable_message=message)
        content = f"{self.wallet.address}:{signed_message.signature.hex()}"

        self.assertIn("x-signature", configured_request.headers)
        self.assertEqual(content, configured_request.headers["x-signature"])

    def test_ws_authenticate(self):
        request: WSJSONRequest = WSJSONRequest(
            payload={"TEST": "SOME_TEST_PAYLOAD"}, throttler_limit_id="TEST_LIMIT_ID", is_auth_required=True
        )

        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = DexalotAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        message = encode_defunct(text="dexalot")
        signed_message = self.wallet.sign_message(signable_message=message)
        content = f"{self.wallet.address}:{signed_message.signature.hex()}"

        signed_request: WSJSONRequest = self.async_run_with_timeout(auth.ws_authenticate(request))

        self.assertIn("signature", signed_request.payload)
        self.assertEqual(content, signed_request.payload["signature"])
