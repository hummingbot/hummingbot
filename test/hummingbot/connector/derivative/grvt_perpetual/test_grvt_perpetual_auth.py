import json
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class GrvtPerpetualAuthTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.auth = GrvtPerpetualAuth(
            api_key="api-key",
            private_key="0x59c6995e998f97a5a0044966f094538e37d1d5cbf1e6fa7e87e55ce49963cf34",  # noqa: mock
            trading_account_id="123456",
            domain="grvt_perpetual",
        )

    async def test_rest_authenticate_adds_cookie_headers(self):
        with patch.object(self.auth, "_ensure_authenticated", AsyncMock()) as ensure_auth:
            self.auth._session_cookie = "gravity-cookie"
            self.auth._grvt_account_id = "account-header-id"
            request = RESTRequest(method=RESTMethod.POST, url="https://example.com", data=json.dumps({}), is_auth_required=True)

            authenticated = await self.auth.rest_authenticate(request)

            ensure_auth.assert_awaited()
            self.assertEqual("gravity=gravity-cookie", authenticated.headers["Cookie"])
            self.assertEqual("account-header-id", authenticated.headers["X-Grvt-Account-Id"])

    async def test_get_order_payload(self):
        with patch("time.time_ns", return_value=1_700_000_000_000_000_000), patch("random.randint", return_value=7):
            payload = self.auth.get_order_payload(
                instrument={"instrument_hash": "0x030501", "base_decimals": 3},
                client_order_id="9223372036854775808",
                exchange_symbol="BTC_USDT_Perp",
                amount=Decimal("1.25"),
                price=Decimal("62000.5"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT_MAKER,
                reduce_only=False,
            )

        order = payload["order"]
        self.assertEqual("123456", order["sub_account_id"])
        self.assertFalse(order["is_market"])
        self.assertTrue(order["post_only"])
        self.assertEqual("GOOD_TILL_TIME", order["time_in_force"])
        self.assertEqual("BTC_USDT_Perp", order["legs"][0]["instrument"])
        self.assertEqual("1.25", order["legs"][0]["size"])
        self.assertEqual("62000.5", order["legs"][0]["limit_price"])
        self.assertEqual("9223372036854775808", order["metadata"]["client_order_id"])
        self.assertEqual(7, order["signature"]["nonce"])
