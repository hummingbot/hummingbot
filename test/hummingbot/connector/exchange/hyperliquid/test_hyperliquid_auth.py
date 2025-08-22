import asyncio
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.hyperliquid.hyperliquid_auth import HyperliquidAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class HyperliquidAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "testApiKey"
        self.secret_key = "13e56ca9cceebf1f33065c2c5376ab38570a114bc1b003b60d838f92be9d7930"  # noqa: mock
        self.use_vault = False  # noqa: mock
        self.trading_required = True  # noqa: mock
        self.auth = HyperliquidAuth(api_key=self.api_key, api_secret=self.secret_key, use_vault=self.use_vault)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        return asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))

    def _get_timestamp(self):
        return 1678974447.926

    @patch("hummingbot.connector.exchange.hyperliquid.hyperliquid_auth._NonceManager.next_ms")
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
            },
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
        params = json.loads(request.data)
        self.assertEqual(4, len(params))
        self.assertEqual(None, params.get("vaultAddress"))
        self.assertEqual("order", params.get("action")["type"])

    @patch("hummingbot.connector.exchange.hyperliquid.hyperliquid_auth._NonceManager.next_ms")
    def test_sign_multiple_orders_has_unique_nonce(self, ts_mock: MagicMock):
        """
        Simulates signing multiple orders quickly to ensure nonce/ts uniqueness
        and prevent duplicate nonce errors.
        """
        base_params = {
            "type": "order",
            "grouping": "na",
            "orders": {
                "asset": 4,
                "isBuy": True,
                "limitPx": 1201,
                "sz": 0.01,
                "reduceOnly": False,
                "orderType": {"limit": {"tif": "Gtc"}},
            },
        }

        # simulate 2 consecutive calls with same timestamp
        ts_mock.return_value = self._get_timestamp()

        requests = []
        for idx in range(2):
            params = dict(base_params)
            params["orders"] = dict(base_params["orders"])
            params["orders"]["cloid"] = f"0x{idx:02x}"
            request = RESTRequest(
                method=RESTMethod.POST,
                url="https://test.url/exchange",
                data=json.dumps(params),
                is_auth_required=True,
            )
            self.async_run_with_timeout(self.auth.rest_authenticate(request))
            requests.append(request)

        # Verify both have unique signed content despite same timestamp
        signed_payloads = [json.loads(req.data) for req in requests]
        self.assertNotEqual(
            signed_payloads[0]["signature"], signed_payloads[1]["signature"],
            "Signatures must differ to avoid duplicate nonce issues"
        )
