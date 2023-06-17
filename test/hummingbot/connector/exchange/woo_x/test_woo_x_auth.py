import asyncio
import hashlib
import hmac
import json
from unittest import TestCase
from unittest.mock import MagicMock

from typing_extensions import Awaitable

from hummingbot.connector.exchange.woo_x.woo_x_auth import WooXAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class WooXAuthTests(TestCase):
    def setUp(self) -> None:
        self._api_key = "testApiKey"
        self._secret = "testSecret"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

        return ret

    def test_rest_authenticate(self):
        mock_time_provider = MagicMock()

        mock_time_provider.time.return_value = 1686452155.0

        data = {
            "symbol": "SPOT_BTC_USDT",
            "order_type": "LIMIT",
            "side": "BUY",
            "order_price": 20000,
            "order_quantity": 1,
        }

        timestamp = str(int(mock_time_provider.time.return_value * 1e3))

        auth = WooXAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)

        request = RESTRequest(method=RESTMethod.POST, data=json.dumps(data), is_auth_required=True)

        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        signable = '&'.join([f"{key}={value}" for key, value in sorted(data.items())]) + f"|{timestamp}"

        signature = (
            hmac.new(
                bytes(self._secret, "utf-8"),
                bytes(signable, "utf-8"),
                hashlib.sha256
            ).hexdigest().upper()
        )

        headers = {
            'x-api-key': self._api_key,
            'x-api-signature': signature,
            'x-api-timestamp': timestamp,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Cache-Control': 'no-cache',
        }

        self.assertEqual(timestamp, configured_request.headers['x-api-timestamp'])

        self.assertEqual(signature, configured_request.headers['x-api-signature'])

        self.assertEqual(headers, configured_request.headers)
