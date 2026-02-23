import asyncio
from typing import Awaitable
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.grvt_perpetual import grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class GrvtPerpetualAuthTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.api_key = "test_api_key"  # noqa: mock
        # Valid 32-byte hex private key for testing
        self.private_key = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f22a3c0e6b7f5d0c1a"  # noqa: mock
        self.sub_account_id = "0"
        self.auth = GrvtPerpetualAuth(
            api_key=self.api_key,
            private_key=self.private_key,
            sub_account_id=self.sub_account_id,
            domain=CONSTANTS.DOMAIN,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_is_mainnet_true(self):
        self.assertTrue(self.auth.is_mainnet)

    def test_is_mainnet_false(self):
        testnet_auth = GrvtPerpetualAuth(
            api_key=self.api_key,
            private_key=self.private_key,
            sub_account_id=self.sub_account_id,
            domain=CONSTANTS.TESTNET_DOMAIN,
        )
        self.assertFalse(testnet_auth.is_mainnet)

    def test_chain_id_mainnet(self):
        self.assertEqual(CONSTANTS.MAINNET_CHAIN_ID, self.auth.chain_id)

    def test_chain_id_testnet(self):
        testnet_auth = GrvtPerpetualAuth(
            api_key=self.api_key,
            private_key=self.private_key,
            sub_account_id=self.sub_account_id,
            domain=CONSTANTS.TESTNET_DOMAIN,
        )
        self.assertEqual(CONSTANTS.TESTNET_CHAIN_ID, testnet_auth.chain_id)

    def test_session_cookie_initially_none(self):
        self.assertIsNone(self.auth.session_cookie)

    def test_account_id_initially_none(self):
        self.assertIsNone(self.auth.account_id)

    def test_get_edge_url_mainnet(self):
        self.assertEqual(CONSTANTS.EDGE_BASE_URL, self.auth._get_edge_url())

    def test_get_edge_url_testnet(self):
        testnet_auth = GrvtPerpetualAuth(
            api_key=self.api_key,
            private_key=self.private_key,
            sub_account_id=self.sub_account_id,
            domain=CONSTANTS.TESTNET_DOMAIN,
        )
        self.assertEqual(CONSTANTS.TESTNET_EDGE_BASE_URL, testnet_auth._get_edge_url())

    def test_sign_order_returns_signature_components(self):
        """Test that sign_order returns dict with r, s, v components."""
        signature = self.auth.sign_order(
            sub_account_id=0,
            is_market=False,
            time_in_force=2,
            post_only=False,
            reduce_only=False,
            asset_id=1,
            contract_size=1000000000,
            limit_price=50000000000000,
            is_buying_contract=True,
            nonce=12345,
            expiration=1700000000,
        )

        self.assertIn("r", signature)
        self.assertIn("s", signature)
        self.assertIn("v", signature)
        self.assertTrue(signature["r"].startswith("0x"))
        self.assertTrue(signature["s"].startswith("0x"))
        self.assertIsInstance(signature["v"], int)

    def test_sign_order_deterministic(self):
        """Test that signing the same order params produces the same signature."""
        params = dict(
            sub_account_id=0,
            is_market=False,
            time_in_force=2,
            post_only=False,
            reduce_only=False,
            asset_id=1,
            contract_size=1000000000,
            limit_price=50000000000000,
            is_buying_contract=True,
            nonce=12345,
            expiration=1700000000,
        )
        sig1 = self.auth.sign_order(**params)
        sig2 = self.auth.sign_order(**params)
        self.assertEqual(sig1, sig2)

    def test_sign_order_different_for_buy_vs_sell(self):
        """Test that buy and sell produce different signatures."""
        common_params = dict(
            sub_account_id=0,
            is_market=False,
            time_in_force=2,
            post_only=False,
            reduce_only=False,
            asset_id=1,
            contract_size=1000000000,
            limit_price=50000000000000,
            nonce=12345,
            expiration=1700000000,
        )
        sig_buy = self.auth.sign_order(is_buying_contract=True, **common_params)
        sig_sell = self.auth.sign_order(is_buying_contract=False, **common_params)
        self.assertNotEqual(sig_buy, sig_sell)

    def test_rest_authenticate_adds_cookie_header(self):
        """Test that rest_authenticate adds Cookie and account ID headers."""
        # Manually set session state
        self.auth._session_cookie = "test_cookie_value"
        self.auth._account_id = "test_account_id"
        self.auth._last_session_time = 9999999999.0  # Far future to skip refresh

        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://trades.grvt.io/full/v1/create_order",
            is_auth_required=True,
        )

        authenticated_request = self.async_run_with_timeout(self.auth.rest_authenticate(request))

        self.assertEqual("gravity=test_cookie_value", authenticated_request.headers["Cookie"])
        self.assertEqual("test_account_id", authenticated_request.headers["X-Grvt-Account-Id"])

    def test_ws_authenticate_passthrough(self):
        """Test that ws_authenticate is a passthrough."""
        request = WSRequest(payload={}, is_auth_required=True)
        result = self.async_run_with_timeout(self.auth.ws_authenticate(request))
        self.assertEqual(request, result)

    def test_get_ws_auth_headers_with_session(self):
        """Test WS auth headers include cookie when session exists."""
        self.auth._session_cookie = "ws_cookie"
        self.auth._account_id = "ws_account"

        headers = self.auth.get_ws_auth_headers()

        self.assertEqual("gravity=ws_cookie", headers["Cookie"])
        self.assertEqual("ws_account", headers["X-Grvt-Account-Id"])

    def test_get_ws_auth_headers_without_session(self):
        """Test WS auth headers are empty when no session exists."""
        headers = self.auth.get_ws_auth_headers()
        self.assertEqual({}, headers)

    def test_get_timestamp_returns_float(self):
        ts = GrvtPerpetualAuth._get_timestamp()
        self.assertIsInstance(ts, float)
        self.assertGreater(ts, 0)
