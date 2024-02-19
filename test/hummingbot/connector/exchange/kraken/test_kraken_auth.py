import asyncio
import base64
import hashlib
import hmac
import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from typing_extensions import Awaitable

from hummingbot.connector.exchange.kraken.kraken_auth import KrakenAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class KrakenAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "kQH5HW/8p1uGOVjbgWA7FunAmGO8lsSUXNsu3eow76sz84Q18fWxnyRzBHCd3pd5nE9qa99HAZtuZuj6F1huXg=="  # noqa: mock

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.exchange.kraken.kraken_auth.KrakenAuth.get_tracking_nonce")
    def test_rest_authenticate(self, mocked_nonce):
        mocked_nonce.return_value = "1"
        now = 1234567890.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now
        test_url = "/test"
        params = {
            "symbol": "LTCBTC",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": "0.1",
        }

        auth = KrakenAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, data=json.dumps(params), is_auth_required=True)
        request.url = test_url
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        # full_params.update({"timestamp": 1234567890000})
        api_secret = base64.b64decode(self._secret)
        api_path: bytes = bytes(request.url, 'utf-8')
        api_nonce: str = "1"
        api_post: str = "nonce=" + api_nonce

        for key, value in params.items():
            api_post += f"&{key}={value}"

        api_sha256: bytes = hashlib.sha256(bytes(api_nonce + api_post, 'utf-8')).digest()
        api_hmac: hmac.HMAC = hmac.new(api_secret, api_path + api_sha256, hashlib.sha512)
        expected_signature: bytes = base64.b64encode(api_hmac.digest())
        #
        # expected_signature = hmac.new(
        #     self._secret.encode("utf-8"),
        #     encoded_params.encode("utf-8"),
        #     hashlib.sha256).hexdigest()
        # self.assertEqual(now * 1e3, configured_request.params["timestamp"])
        self.assertEqual(str(expected_signature, 'utf-8'), configured_request.headers["API-Sign"])
        self.assertEqual(self._api_key, configured_request.headers["API-Key"])
