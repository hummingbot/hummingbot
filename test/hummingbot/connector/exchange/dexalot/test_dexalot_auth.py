from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import MagicMock

from eth_account import Account
from eth_account.messages import encode_defunct

from hummingbot.connector.exchange.dexalot.dexalot_auth import DexalotAuth
from hummingbot.connector.utils import to_0x_hex
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest


class DexalotAuthTests(IsolatedAsyncioWrapperTestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.wallet = Account.from_key(self._secret)

    async def test_rest_authenticate(self):
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = DexalotAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, params={}, is_auth_required=True)
        configured_request = await (auth.rest_authenticate(request))

        message = encode_defunct(text="dexalot")
        signed_message = to_0x_hex(self.wallet.sign_message(signable_message=message).signature)
        content = f"{self.wallet.address}:{signed_message}"

        self.assertIn("x-signature", configured_request.headers)
        self.assertEqual(configured_request.headers["x-signature"], content)

    async def test_ws_authenticate(self):
        request: WSJSONRequest = WSJSONRequest(
            payload={"TEST": "SOME_TEST_PAYLOAD"}, throttler_limit_id="TEST_LIMIT_ID", is_auth_required=True
        )

        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        auth = DexalotAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        message = encode_defunct(text="dexalot")
        signed_message = to_0x_hex(self.wallet.sign_message(signable_message=message).signature)
        content = f"{self.wallet.address}:{signed_message}"

        signed_request: WSJSONRequest = await (auth.ws_authenticate(request))

        self.assertIn("signature", signed_request.payload)
        self.assertEqual(content, signed_request.payload["signature"])
