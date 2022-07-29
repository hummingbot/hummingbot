import asyncio
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

from hummingbot.connector.exchange.btse.btse_auth import BtseAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class BtseAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "4e9536c79f0fdd72bf04f2430982d3f61d9d76c996f0175bbba470d69d59816x" # noqa: mock
        self._secret = "848db84ac252b6726e5f6e7a711d9c96d9fd77d020151b45839a5b59c37203bx"  # noqa: mock

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1624985375.123
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now
        sign = 'e9cd0babdf497b536d1e48bc9cf1fadad3426b36406b5747d77ae4e3cdc9ab556863f2d0cf78e0228c39a064ad43afb7' # noqa: mock

        url = '/api/v3.2/order'
        params = {
            "postOnly": False,
            "price": 8500.0,
            "side": "BUY",
            "size": 0.002,
            "stopPrice": 0.0,
            "symbol": "BTC-USD",
            "time_in_force": "GTC",
            "trailValue": 0.0,
            "triggerPrice": 0.0,
            "txType": "LIMIT",
            "type": "LIMIT"
        }

        auth = BtseAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, url=url, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        self.assertEqual(now * 1e3, configured_request.headers["btse-nonce"])
        self.assertEqual(sign, configured_request.headers["btse-sign"])
        self.assertEqual(self._api_key, configured_request.headers['btse-api'])
