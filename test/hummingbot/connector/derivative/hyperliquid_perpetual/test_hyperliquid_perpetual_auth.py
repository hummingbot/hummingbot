import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import HyperliquidPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class HyperliquidPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930" # noqa: mock
        self.use_vault = False # noqa: mock
        self.auth = HyperliquidPerpetualAuth(api_key=self.api_key, api_secret=self.secret_key, use_vault=self.use_vault)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _get_timestamp(self):
        return 1678974447.926

    @patch(
        "hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth.HyperliquidPerpetualAuth._get_timestamp")
    def test_sign_order_params_post_request(self, ts_mock: MagicMock):
        params = {
            "type": "order",
            "grouping": "na",
            "orders": {
                "asset": 4,
                "isBuy": True,
                "limitPx": 1201,
                "sz": 0.01,
                "reduceOnly": False,
                "orderType": {"limit": {"tif": "Gtc"}},
                "cloid": "0x000000000000000000000000000ee056",
            }
        }
        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://test.url/exchange",
            data=json.dumps(params),
            is_auth_required=True,
        )
        timestamp = self._get_timestamp()
        ts_mock.return_value = timestamp

        self.async_run_with_timeout(self.auth.rest_authenticate(request))
        # raw_signature = f'/linear/v1/orders&one=1&timestamp={int(self._get_timestamp() * 1e3)}'
        # expected_signature = hmac.new(bytes(self.secret_key.encode("utf-8")),
        #                               raw_signature.encode("utf-8"),
        #                               hashlib.sha256).hexdigest()

        params = json.loads(request.data)
        self.assertEqual(4, len(params))
        self.assertEqual(None, params.get("vaultAddress"))
        self.assertEqual("order", params.get("action")["type"])
