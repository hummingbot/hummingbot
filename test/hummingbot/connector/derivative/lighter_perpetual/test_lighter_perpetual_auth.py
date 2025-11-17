import sys
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest, WSRequest


class LighterPerpetualAuthTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.signer = MagicMock()
        self.signer.create_auth_token_with_expiry = MagicMock(
            return_value=("token", None)
        )
        self.signer.sign_create_order = AsyncMock(return_value=("create", "sig", None))
        self.signer.sign_cancel_order = AsyncMock(return_value=("cancel", "sig", None))
        self.signer.sign_cancel_all_orders = AsyncMock(
            return_value=("cancel_all", "sig", None)
        )
        self.signer.sign_update_leverage = AsyncMock(
            return_value=("leverage", "sig", None)
        )
        self.signer.sign_withdraw = AsyncMock(return_value=("withdraw", "sig", None))
        self.auth = LighterPerpetualAuth(
            domain=CONSTANTS.DEFAULT_DOMAIN,
            api_key_private_key="0xabc",
            account_index=3,
            api_key_index=5,
            eth_private_key=None,
            signer_factory=self._build_signer_factory(),
        )

    def _build_signer_factory(self):
        def factory(**kwargs):
            self.factory_arguments = kwargs
            return self.signer

        return factory

    async def test_rest_authenticate_returns_same_request(self):
        request = RESTRequest(method=RESTMethod.GET, url="https://example.com")
        result = await self.auth.rest_authenticate(request)
        self.assertIs(request, result)

    async def test_ws_authenticate_returns_same_request(self):
        request = WSJSONRequest(payload={"type": "ping"})
        result = await self.auth.ws_authenticate(request)
        self.assertIs(request, result)

    async def test_create_auth_token_calls_signer(self):
        token = await self.auth.create_auth_token(expiry_seconds=120)
        self.signer.create_auth_token_with_expiry.assert_called_once_with(120)
        self.assertEqual("token", token)

    async def test_create_auth_token_raises_on_error(self):
        self.signer.create_auth_token_with_expiry.return_value = (None, "boom")
        with self.assertRaises(RuntimeError):
            await self.auth.create_auth_token()

    async def test_sign_create_order_returns_signer_result(self):
        result = await self.auth.sign_create_order(market_id=1)
        self.signer.sign_create_order.assert_awaited_once_with(market_id=1)
        self.assertEqual(("create", "sig", None), result)

    async def test_sign_cancel_order_returns_signer_result(self):
        result = await self.auth.sign_cancel_order(market_id=1)
        self.signer.sign_cancel_order.assert_awaited_once_with(market_id=1)
        self.assertEqual(("cancel", "sig", None), result)

    async def test_sign_cancel_all_orders_returns_signer_result(self):
        result = await self.auth.sign_cancel_all_orders(market_id=1)
        self.signer.sign_cancel_all_orders.assert_awaited_once_with(market_id=1)
        self.assertEqual(("cancel_all", "sig", None), result)

    async def test_sign_update_leverage_returns_signer_result(self):
        result = await self.auth.sign_update_leverage(market_id=1)
        self.signer.sign_update_leverage.assert_awaited_once_with(market_id=1)
        self.assertEqual(("leverage", "sig", None), result)

    async def test_sign_withdraw_invokes_signer(self):
        auth = LighterPerpetualAuth(
            domain=CONSTANTS.DEFAULT_DOMAIN,
            api_key_private_key="0xdef",
            account_index=8,
            api_key_index=4,
            signer_factory=self._build_signer_factory(),
        )
        result = await auth.sign_withdraw(usdc_amount=10)
        self.signer.sign_withdraw.assert_awaited_once_with(usdc_amount=10)
        self.assertEqual(("withdraw", "sig", None), result)

    def test_signer_factory_receives_expected_arguments(self):
        _ = self.auth.signer  # trigger factory invocation
        expected_base_url = CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN]
        self.assertEqual(
            {
                "base_url": expected_base_url,
                "api_key_private_key": "0xabc",
                "account_index": 3,
                "api_key_index": 5,
                "max_api_key_index": 5,
                "additional_private_keys": {},
                "eth_private_key": None,
            },
            self.factory_arguments,
        )

    def test_default_signer_factory_imports_signer_client(self):
        module_name = "lighter.signer_client"
        signer_instance = MagicMock()
        mock_signer_class = MagicMock(return_value=signer_instance)
        mock_module = MagicMock()
        mock_module.SignerClient = mock_signer_class
        sys.modules.pop(module_name, None)
        with patch.dict("sys.modules", {module_name: mock_module}, clear=False):
            auth = LighterPerpetualAuth(
                domain=CONSTANTS.DEFAULT_DOMAIN,
                api_key_private_key="0x123",
                account_index=1,
                api_key_index=0,
            )
            self.assertIs(auth.signer, signer_instance)
        mock_signer_class.assert_called_once_with(
            url=CONSTANTS.REST_URLS[CONSTANTS.DEFAULT_DOMAIN],
            private_key="0x123",
            account_index=1,
            api_key_index=0,
            max_api_key_index=0,
            private_keys={},
        )
