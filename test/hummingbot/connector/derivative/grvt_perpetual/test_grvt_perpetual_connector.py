"""
Basic unit tests for the GRVT Perpetual connector.

These tests verify that the connector's core components behave correctly
without requiring live network connections to the GRVT exchange.
"""
import asyncio
import json
import time
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_auth import GrvtPerpetualAuth
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_derivative import GrvtPerpetualDerivative
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------

class TestGrvtPerpetualAuth(unittest.TestCase):
    """Unit tests for GrvtPerpetualAuth."""

    def setUp(self):
        self.api_key = "test_api_key_abc"
        self.sub_account_id = "12345678901234567"
        self.time_sync = TimeSynchronizer()
        self.time_sync.add_time_offset_ms_sample(0)
        self.auth = GrvtPerpetualAuth(
            api_key=self.api_key,
            sub_account_id=self.sub_account_id,
            time_provider=self.time_sync,
        )

    def test_initial_state(self):
        self.assertEqual(self.sub_account_id, self.auth.sub_account_id)
        self.assertIsNone(self.auth.session_cookie)
        self.assertIsNone(self.auth.account_id)
        self.assertFalse(self.auth._authenticated)

    def test_set_session_cookie(self):
        cookie = "gravity=abc123token"
        self.auth.set_session_cookie(cookie)
        self.assertEqual(cookie, self.auth.session_cookie)

    def test_set_account_id(self):
        account_id = "0xDEADBEEF"
        self.auth.set_account_id(account_id)
        self.assertEqual(account_id, self.auth.account_id)

    def test_extract_session_cookie_from_set_cookie_header(self):
        header = "gravity=mytoken123; Path=/; HttpOnly; Secure"
        result = GrvtPerpetualAuth._extract_session_cookie(header, {})
        self.assertEqual("gravity=mytoken123", result)

    def test_extract_session_cookie_from_response_json(self):
        result = GrvtPerpetualAuth._extract_session_cookie("", {"cookie": "gravity=jsontoken; Path=/"})
        self.assertEqual("gravity=jsontoken", result)

    def test_extract_session_cookie_returns_none_when_absent(self):
        result = GrvtPerpetualAuth._extract_session_cookie("", {})
        self.assertIsNone(result)

    def test_get_auth_login_body(self):
        body = self.auth.get_auth_login_body()
        parsed = json.loads(body)
        self.assertEqual(self.api_key, parsed["api_key"])

    def test_header_for_authentication_without_cookie(self):
        headers = self.auth.header_for_authentication()
        self.assertEqual("application/json", headers["Content-Type"])
        self.assertNotIn("Cookie", headers)
        self.assertEqual(self.sub_account_id, headers["X-Grvt-Subaccount-Id"])

    def test_header_for_authentication_with_cookie_and_account_id(self):
        self.auth.set_session_cookie("gravity=tok")
        self.auth.set_account_id("0xABC")
        headers = self.auth.header_for_authentication()
        self.assertEqual("gravity=tok", headers["Cookie"])
        self.assertEqual("0xABC", headers["X-Grvt-Account-Id"])
        self.assertEqual(self.sub_account_id, headers["X-Grvt-Subaccount-Id"])

    def test_ws_headers_for_authentication(self):
        self.auth.set_session_cookie("gravity=tok")
        self.auth.set_account_id("0xABC")
        headers = self.auth.ws_headers_for_authentication()
        self.assertEqual("gravity=tok", headers["Cookie"])
        self.assertEqual("0xABC", headers["X-Grvt-Account-Id"])
        self.assertEqual(self.sub_account_id, headers["X-Grvt-Subaccount-Id"])

    def test_ensure_authenticated_with_preset_cookie(self):
        self.auth.set_session_cookie("gravity=preset_token")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.auth.ensure_authenticated())
        self.assertTrue(self.auth._authenticated)
        loop.close()

    def test_rest_authenticate_adds_required_headers(self):
        self.auth.set_session_cookie("gravity=tok")
        self.auth.set_account_id("0xACCOUNT")
        self.auth._authenticated = True

        request = RESTRequest(
            method=RESTMethod.POST,
            url="https://trades.grvt.io/full/v1/create_order",
        )
        request.headers = {}

        loop = asyncio.new_event_loop()
        authenticated = loop.run_until_complete(self.auth.rest_authenticate(request))
        loop.close()

        self.assertEqual("application/json", authenticated.headers["Content-Type"])
        self.assertEqual("gravity=tok", authenticated.headers["Cookie"])
        self.assertEqual("0xACCOUNT", authenticated.headers["X-Grvt-Account-Id"])
        self.assertEqual(self.sub_account_id, authenticated.headers["X-Grvt-Subaccount-Id"])

    def test_initializes_with_testnet_domain(self):
        testnet_auth = GrvtPerpetualAuth(
            api_key=self.api_key,
            sub_account_id=self.sub_account_id,
            time_provider=self.time_sync,
            domain=CONSTANTS.TESTNET_DOMAIN,
        )
        self.assertEqual(CONSTANTS.TESTNET_DOMAIN, testnet_auth._domain)


# ---------------------------------------------------------------------------
# Web utils tests
# ---------------------------------------------------------------------------

class TestGrvtPerpetualWebUtils(unittest.TestCase):
    """Unit tests for grvt_perpetual_web_utils."""

    def test_public_rest_url_mainnet(self):
        url = web_utils.public_rest_url("all_instruments", domain=CONSTANTS.DOMAIN)
        self.assertIn("market-data.grvt.io", url)
        self.assertIn("all_instruments", url)

    def test_public_rest_url_testnet(self):
        url = web_utils.public_rest_url("all_instruments", domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertIn("testnet", url)

    def test_private_rest_url_mainnet(self):
        url = web_utils.private_rest_url("create_order", domain=CONSTANTS.DOMAIN)
        self.assertIn("trades.grvt.io", url)
        self.assertIn("create_order", url)

    def test_private_rest_url_testnet(self):
        url = web_utils.private_rest_url("create_order", domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertIn("testnet", url)

    def test_auth_url_mainnet(self):
        url = web_utils.auth_url(domain=CONSTANTS.DOMAIN)
        self.assertIn("edge.grvt.io", url)

    def test_auth_url_testnet(self):
        url = web_utils.auth_url(domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertIn("testnet", url)

    def test_wss_url_mainnet(self):
        url = web_utils.wss_url(domain=CONSTANTS.DOMAIN)
        self.assertTrue(url.startswith("wss://"))
        self.assertIn("market-data.grvt.io", url)

    def test_trade_wss_url_mainnet(self):
        url = web_utils.trade_wss_url(domain=CONSTANTS.DOMAIN)
        self.assertTrue(url.startswith("wss://"))
        self.assertIn("trades.grvt.io", url)

    def test_convert_to_exchange_trading_pair(self):
        result = web_utils.convert_to_exchange_trading_pair("BTC-USDT")
        self.assertEqual("BTC_USDT_Perp", result)

    def test_convert_from_exchange_trading_pair(self):
        result = web_utils.convert_from_exchange_trading_pair("BTC_USDT_Perp")
        self.assertEqual("BTC-USDT", result)

    def test_convert_from_exchange_trading_pair_non_perp(self):
        # Non-Perp symbols are returned as-is
        result = web_utils.convert_from_exchange_trading_pair("SOMETHING_INVALID")
        self.assertEqual("SOMETHING_INVALID", result)

    def test_is_exchange_information_valid_perpetual(self):
        rule = {"instrument": "BTC_USDT_Perp", "kind": "PERPETUAL"}
        self.assertTrue(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_non_perpetual(self):
        rule = {"instrument": "BTC_USDT_Future", "kind": "FUTURE"}
        self.assertFalse(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_with_is_active_false(self):
        rule = {"instrument": "BTC_USDT_Perp", "kind": "PERPETUAL", "is_active": False}
        self.assertFalse(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_with_status_active(self):
        rule = {"instrument": "BTC_USDT_Perp", "kind": "PERPETUAL", "status": "active"}
        self.assertTrue(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_with_status_trading(self):
        rule = {"instrument": "ETH_USDT_Perp", "kind": "PERPETUAL", "status": "trading"}
        self.assertTrue(web_utils.is_exchange_information_valid(rule))


# ---------------------------------------------------------------------------
# Order sign utils tests
# ---------------------------------------------------------------------------

class TestGrvtPerpetualOrderSignUtils(unittest.TestCase):
    """Unit tests for grvt_perpetual_order_sign_utils.build_order_signature."""

    # Known test private key from Hardhat / well-known dev key
    PRIVATE_KEY = "0x59c6995e998f97a5a0044966f094538ce5f9ac8f6d44ed77f5b7f31f6f6e4d31"  # noqa: mock

    def test_build_order_signature_returns_required_fields(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_order_sign_utils import (
            build_order_signature,
        )

        # BTC_USDT_Perp instrument_hash (fake but structurally valid)
        instrument_hash = "0x" + "1" * 64

        sig = build_order_signature(
            private_key=self.PRIVATE_KEY,
            domain=CONSTANTS.TESTNET_DOMAIN,
            sub_account_id="12345678",
            instrument_hash=instrument_hash,
            base_decimals=9,
            is_market=False,
            time_in_force=CONSTANTS.TIME_IN_FORCE_GTC,
            post_only=False,
            reduce_only=False,
            is_buying_contract=True,
            size=Decimal("0.001"),
            limit_price=Decimal("50000"),
        )

        self.assertIn("r", sig)
        self.assertIn("s", sig)
        self.assertIn("v", sig)
        self.assertIn("expiration", sig)
        self.assertIn("nonce", sig)
        self.assertIn("signer", sig)

        # r and s should be 0x-prefixed 32-byte hex
        self.assertTrue(sig["r"].startswith("0x"))
        self.assertTrue(sig["s"].startswith("0x"))
        self.assertIn(sig["v"], (27, 28))

    def test_build_order_signature_raises_on_missing_instrument_hash(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_order_sign_utils import (
            build_order_signature,
        )

        with self.assertRaises(ValueError):
            build_order_signature(
                private_key=self.PRIVATE_KEY,
                domain=CONSTANTS.TESTNET_DOMAIN,
                sub_account_id="12345678",
                instrument_hash=None,
                base_decimals=9,
                is_market=False,
                time_in_force=CONSTANTS.TIME_IN_FORCE_GTC,
                post_only=False,
                reduce_only=False,
                is_buying_contract=True,
                size=Decimal("0.001"),
                limit_price=Decimal("50000"),
            )

    def test_build_order_signature_raises_on_invalid_tif(self):
        from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_order_sign_utils import (
            build_order_signature,
        )

        with self.assertRaises(ValueError):
            build_order_signature(
                private_key=self.PRIVATE_KEY,
                domain=CONSTANTS.TESTNET_DOMAIN,
                sub_account_id="12345678",
                instrument_hash="0x" + "1" * 64,
                base_decimals=9,
                is_market=False,
                time_in_force="INVALID_TIF",
                post_only=False,
                reduce_only=False,
                is_buying_contract=True,
                size=Decimal("0.001"),
                limit_price=Decimal("50000"),
            )


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------

class TestGrvtPerpetualConstants(unittest.TestCase):
    """Verify constants are set correctly."""

    def test_domain_value(self):
        self.assertEqual("grvt_perpetual", CONSTANTS.DOMAIN)

    def test_testnet_domain_value(self):
        self.assertEqual("grvt_perpetual_testnet", CONSTANTS.TESTNET_DOMAIN)

    def test_time_in_force_constants(self):
        self.assertEqual("GOOD_TILL_TIME", CONSTANTS.TIME_IN_FORCE_GTC)
        self.assertEqual("IMMEDIATE_OR_CANCEL", CONSTANTS.TIME_IN_FORCE_IOC)
        self.assertEqual("FILL_OR_KILL", CONSTANTS.TIME_IN_FORCE_FOK)

    def test_order_state_mapping_coverage(self):
        from hummingbot.core.data_type.in_flight_order import OrderState
        expected_keys = {"PENDING", "OPEN", "FILLED", "PARTIALLY_FILLED", "CANCELLED", "CANCELED", "REJECTED", "EXPIRED"}
        for key in expected_keys:
            self.assertIn(key, CONSTANTS.ORDER_STATE, f"Missing order state key: {key}")

    def test_rate_limits_non_empty(self):
        self.assertGreater(len(CONSTANTS.RATE_LIMITS), 0)

    def test_url_constants(self):
        self.assertIn("https://", CONSTANTS.PERPETUAL_BASE_URL)
        self.assertIn("https://", CONSTANTS.MARKET_DATA_BASE_URL)
        self.assertIn("wss://", CONSTANTS.PERPETUAL_WS_URL)
        self.assertIn("wss://", CONSTANTS.PERPETUAL_TRADE_WS_URL)


# ---------------------------------------------------------------------------
# Derivative connector unit tests
# ---------------------------------------------------------------------------

class TestGrvtPerpetualDerivative(unittest.TestCase):
    """Unit tests for GrvtPerpetualDerivative."""

    PRIVATE_KEY = "0x59c6995e998f97a5a0044966f094538ce5f9ac8f6d44ed77f5b7f31f6f6e4d31"  # noqa: mock

    def _build_connector(self, domain=CONSTANTS.TESTNET_DOMAIN) -> GrvtPerpetualDerivative:
        connector = GrvtPerpetualDerivative(
            grvt_perpetual_api_key="test_api_key",
            grvt_perpetual_sub_account_id="12345678901234567",
            grvt_perpetual_private_key=self.PRIVATE_KEY,
            trading_pairs=["BTC-USDT"],
            domain=domain,
        )
        connector._auth.set_session_cookie("gravity=test_cookie")
        connector._auth.set_account_id("0xTESTACCOUNT")
        connector._auth._authenticated = True
        connector._set_trading_pair_symbol_map(
            bidict({"BTC_USDT_Perp": "BTC-USDT"})
        )
        return connector

    def test_connector_name(self):
        connector = self._build_connector()
        self.assertEqual("grvt_perpetual", connector.name)

    def test_supported_order_types(self):
        from hummingbot.core.data_type.common import OrderType
        connector = self._build_connector()
        order_types = connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.MARKET, order_types)
        self.assertIn(OrderType.LIMIT_MAKER, order_types)

    def test_supported_position_modes(self):
        from hummingbot.core.data_type.common import PositionMode
        connector = self._build_connector()
        modes = connector.supported_position_modes()
        self.assertEqual([PositionMode.ONEWAY], modes)

    def test_is_cancel_request_synchronous(self):
        connector = self._build_connector()
        self.assertTrue(connector.is_cancel_request_in_exchange_synchronous)

    def test_domain_property(self):
        connector = self._build_connector(domain=CONSTANTS.TESTNET_DOMAIN)
        self.assertEqual(CONSTANTS.TESTNET_DOMAIN, connector.domain)

    def test_trading_pairs_property(self):
        connector = self._build_connector()
        self.assertIn("BTC-USDT", connector.trading_pairs)

    def test_extract_result_list_from_list(self):
        response = [{"instrument": "BTC_USDT_Perp"}, {"instrument": "ETH_USDT_Perp"}]
        result = GrvtPerpetualDerivative._extract_result_list(response)
        self.assertEqual(2, len(result))

    def test_extract_result_list_from_results_key(self):
        response = {"results": [{"instrument": "BTC_USDT_Perp"}]}
        result = GrvtPerpetualDerivative._extract_result_list(response)
        self.assertEqual(1, len(result))
        self.assertEqual("BTC_USDT_Perp", result[0]["instrument"])

    def test_extract_result_list_from_direct_instrument(self):
        response = {"instrument": "BTC_USDT_Perp"}
        result = GrvtPerpetualDerivative._extract_result_list(response)
        self.assertEqual(1, len(result))

    def test_extract_result_list_empty_on_non_dict_non_list(self):
        result = GrvtPerpetualDerivative._extract_result_list("not a dict")
        self.assertEqual([], result)

    def test_exchange_symbol_for_trading_pair_fallback(self):
        connector = self._build_connector()
        # Clear the symbol map to force fallback
        connector._set_trading_pair_symbol_map(bidict())
        loop = asyncio.new_event_loop()
        symbol = loop.run_until_complete(
            connector.exchange_symbol_for_trading_pair("BTC-USDT")
        )
        loop.close()
        self.assertEqual("BTC_USDT_Perp", symbol)

    def test_format_trading_rules(self):
        connector = self._build_connector()
        exchange_info = {
            "results": [
                {
                    "instrument": "BTC_USDT_Perp",
                    "kind": "PERPETUAL",
                    "tick_size": "0.1",
                    "min_size": "0.001",
                    "size_increment": "0.001",
                    "min_notional": "10",
                    "quote": "USDT",
                }
            ]
        }
        loop = asyncio.new_event_loop()
        rules = loop.run_until_complete(connector._format_trading_rules(exchange_info))
        loop.close()

        self.assertEqual(1, len(rules))
        self.assertEqual("BTC-USDT", rules[0].trading_pair)
        self.assertEqual(Decimal("0.001"), rules[0].min_order_size)
        self.assertEqual(Decimal("0.1"), rules[0].min_price_increment)
        self.assertEqual("USDT", rules[0].buy_order_collateral_token)

    def test_initialize_trading_pair_symbols_from_exchange_info(self):
        connector = self._build_connector()
        exchange_info = {
            "results": [
                {
                    "instrument": "BTC_USDT_Perp",
                    "kind": "PERPETUAL",
                    "base": "BTC",
                    "quote": "USDT",
                }
            ]
        }
        connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)
        # After init, the symbol map should contain BTC_USDT_Perp -> BTC-USDT
        self.assertIn("BTC_USDT_Perp", connector._instrument_info_by_symbol)

    def test_order_not_found_error_detection(self):
        connector = self._build_connector()
        exception = Exception(
            f"{CONSTANTS.ORDER_NOT_EXIST_ERROR_CODE} - {CONSTANTS.ORDER_NOT_EXIST_MESSAGE}"
        )
        self.assertTrue(connector._is_order_not_found_during_status_update_error(exception))

    def test_unknown_order_error_detection(self):
        connector = self._build_connector()
        exception = Exception(
            f"{CONSTANTS.UNKNOWN_ORDER_ERROR_CODE} - {CONSTANTS.UNKNOWN_ORDER_MESSAGE}"
        )
        self.assertTrue(connector._is_order_not_found_during_cancelation_error(exception))

    def test_get_position_mode_returns_oneway(self):
        connector = self._build_connector()
        loop = asyncio.new_event_loop()
        mode = loop.run_until_complete(connector._get_position_mode())
        loop.close()
        from hummingbot.core.data_type.common import PositionMode
        self.assertEqual(PositionMode.ONEWAY, mode)

    def test_trading_pair_position_mode_set_oneway_succeeds(self):
        connector = self._build_connector()
        from hummingbot.core.data_type.common import PositionMode
        loop = asyncio.new_event_loop()
        success, msg = loop.run_until_complete(
            connector._trading_pair_position_mode_set(PositionMode.ONEWAY, "BTC-USDT")
        )
        loop.close()
        self.assertTrue(success)

    def test_trading_pair_position_mode_set_hedge_fails(self):
        connector = self._build_connector()
        from hummingbot.core.data_type.common import PositionMode
        loop = asyncio.new_event_loop()
        success, msg = loop.run_until_complete(
            connector._trading_pair_position_mode_set(PositionMode.HEDGE, "BTC-USDT")
        )
        loop.close()
        self.assertFalse(success)
        self.assertIn("one-way", msg)


# ---------------------------------------------------------------------------
# Integration-style tests (mock HTTP)
# ---------------------------------------------------------------------------

class TestGrvtPerpetualDerivativeMocked(unittest.IsolatedAsyncioTestCase):
    """Async tests that mock HTTP calls."""

    PRIVATE_KEY = "0x59c6995e998f97a5a0044966f094538ce5f9ac8f6d44ed77f5b7f31f6f6e4d31"  # noqa: mock

    def setUp(self):
        self.connector = GrvtPerpetualDerivative(
            grvt_perpetual_api_key="test_api_key",
            grvt_perpetual_sub_account_id="12345678901234567",
            grvt_perpetual_private_key=self.PRIVATE_KEY,
            trading_pairs=["BTC-USDT"],
            domain=CONSTANTS.TESTNET_DOMAIN,
        )
        self.connector._auth.set_session_cookie("gravity=test_cookie")
        self.connector._auth.set_account_id("0xTESTACCOUNT")
        self.connector._auth._authenticated = True
        self.connector._set_trading_pair_symbol_map(
            bidict({"BTC_USDT_Perp": "BTC-USDT"})
        )

    async def test_update_balances_processes_response(self):
        mock_response = {
            "result": {
                "available_balance": "1000.50",
                "settle_currency": "USDT",
                "spot_balances": [
                    {"currency": "USDT", "balance": "1500.00"},
                    {"currency": "BTC", "balance": "0.05"},
                ],
            }
        }

        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            await self.connector._update_balances()

        self.assertIn("USDT", self.connector._account_balances)
        self.assertEqual(Decimal("1500.00"), self.connector._account_balances["USDT"])
        self.assertEqual(Decimal("1000.50"), self.connector._account_available_balances["USDT"])
        self.assertIn("BTC", self.connector._account_balances)
        self.assertEqual(Decimal("0.05"), self.connector._account_balances["BTC"])

    async def test_update_balances_removes_stale_assets(self):
        self.connector._account_balances["STALE_COIN"] = Decimal("999")
        self.connector._account_available_balances["STALE_COIN"] = Decimal("999")

        mock_response = {
            "result": {
                "available_balance": "100",
                "settle_currency": "USDT",
                "spot_balances": [{"currency": "USDT", "balance": "100"}],
            }
        }

        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            await self.connector._update_balances()

        self.assertNotIn("STALE_COIN", self.connector._account_balances)

    async def test_update_positions_creates_position(self):
        mock_response = {
            "results": [
                {
                    "instrument": "BTC_USDT_Perp",
                    "size": "0.5",
                    "entry_price": "45000",
                    "unrealized_pnl": "100",
                    "leverage": "5",
                }
            ]
        }

        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            await self.connector._update_positions()

        from hummingbot.core.data_type.common import PositionSide
        pos_key = self.connector._perpetual_trading.position_key("BTC-USDT", PositionSide.BOTH)
        positions = self.connector._perpetual_trading.get_position(pos_key)
        self.assertIsNotNone(positions)

    async def test_update_positions_removes_zero_position(self):
        from hummingbot.core.data_type.common import PositionSide
        from hummingbot.connector.derivative.position import Position

        pos_key = self.connector._perpetual_trading.position_key("BTC-USDT", PositionSide.BOTH)
        self.connector._perpetual_trading.set_position(
            pos_key,
            Position("BTC-USDT", PositionSide.BOTH, Decimal("100"), Decimal("45000"), Decimal("0.5"), Decimal("5")),
        )

        mock_response = {
            "results": [
                {
                    "instrument": "BTC_USDT_Perp",
                    "size": "0",
                    "entry_price": "45000",
                    "unrealized_pnl": "0",
                    "leverage": "5",
                }
            ]
        }

        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            await self.connector._update_positions()

        self.assertIsNone(self.connector._perpetual_trading.get_position(pos_key))

    async def test_get_last_traded_price(self):
        mock_response = {"result": {"last_price": "50123.45"}}
        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            price = await self.connector._get_last_traded_price("BTC-USDT")
        self.assertAlmostEqual(50123.45, price, places=2)

    async def test_set_trading_pair_leverage(self):
        mock_response = {"result": {}}
        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            success, msg = await self.connector._set_trading_pair_leverage("BTC-USDT", 10)
        self.assertTrue(success)
        self.assertEqual("", msg)

    async def test_set_trading_pair_leverage_error(self):
        mock_response = {"code": 1234, "message": "Leverage too high"}
        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            success, msg = await self.connector._set_trading_pair_leverage("BTC-USDT", 999)
        self.assertFalse(success)
        self.assertIn("Leverage too high", msg)

    async def test_process_order_event_updates_tracked_order(self):
        from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
        from hummingbot.core.data_type.common import TradeType, OrderType

        tracked_order = InFlightOrder(
            client_order_id="test_order_001",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("0.001"),
            creation_timestamp=time.time(),
            price=Decimal("50000"),
            exchange_order_id="exchange_001",
        )
        self.connector._order_tracker.start_tracking_order(tracked_order)

        order_data = {
            "order_id": "exchange_001",
            "metadata": {"client_order_id": "test_order_001"},
            "state": {
                "status": "FILLED",
                "update_time": str(int(time.time() * 1e9)),
            },
        }

        await self.connector._process_order_event(order_data)
        updated = self.connector._order_tracker.all_orders.get("test_order_001")
        self.assertIsNotNone(updated)

    async def test_process_position_event_creates_position(self):
        position_data = {
            "instrument": "BTC_USDT_Perp",
            "size": "0.1",
            "entry_price": "50000",
            "unrealized_pnl": "50",
            "leverage": "10",
        }
        await self.connector._process_position_event(position_data)
        from hummingbot.core.data_type.common import PositionSide
        pos_key = self.connector._perpetual_trading.position_key("BTC-USDT", PositionSide.BOTH)
        pos = self.connector._perpetual_trading.get_position(pos_key)
        self.assertIsNotNone(pos)
        self.assertEqual(Decimal("0.1"), pos.amount)

    async def test_process_position_event_removes_zero_position(self):
        from hummingbot.core.data_type.common import PositionSide
        from hummingbot.connector.derivative.position import Position

        pos_key = self.connector._perpetual_trading.position_key("BTC-USDT", PositionSide.BOTH)
        self.connector._perpetual_trading.set_position(
            pos_key,
            Position("BTC-USDT", PositionSide.BOTH, Decimal("50"), Decimal("50000"), Decimal("0.1"), Decimal("10")),
        )

        position_data = {
            "instrument": "BTC_USDT_Perp",
            "size": "0",
            "entry_price": "50000",
            "unrealized_pnl": "0",
            "leverage": "10",
        }
        await self.connector._process_position_event(position_data)
        self.assertIsNone(self.connector._perpetual_trading.get_position(pos_key))

    async def test_fetch_last_fee_payment_no_payments(self):
        mock_empty = {"results": []}
        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_empty)):
            ts, rate, payment = await self.connector._fetch_last_fee_payment("BTC-USDT")
        self.assertEqual(0, ts)
        self.assertEqual(Decimal("-1"), rate)
        self.assertEqual(Decimal("-1"), payment)

    async def test_fetch_last_fee_payment_with_data(self):
        now_ns = int(time.time() * 1e9)
        payment_response = {
            "results": [{"payment": "5.25", "event_time": str(now_ns)}]
        }
        rate_response = {
            "results": [{"funding_rate": "0.0001"}]
        }
        call_count = 0

        async def mock_api_post(path_url, data, is_auth_required=False):
            nonlocal call_count
            call_count += 1
            if path_url == CONSTANTS.FUNDING_PAYMENT_HISTORY_URL:
                return payment_response
            return rate_response

        with patch.object(self.connector, "_api_post", side_effect=mock_api_post):
            ts, rate, payment = await self.connector._fetch_last_fee_payment("BTC-USDT")

        self.assertGreater(ts, 0)
        self.assertEqual(Decimal("0.0001"), rate)
        self.assertEqual(Decimal("5.25"), payment)

    async def test_request_order_status_with_code_in_response(self):
        """When exchange returns an error code, preserve current order state."""
        from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState
        from hummingbot.core.data_type.common import TradeType, OrderType

        tracked_order = InFlightOrder(
            client_order_id="order_abc",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("0.001"),
            creation_timestamp=time.time(),
            price=Decimal("50000"),
        )

        mock_response = {"code": 1002, "message": "Order does not exist"}
        with patch.object(self.connector, "_api_post", new=AsyncMock(return_value=mock_response)):
            update = await self.connector._request_order_status(tracked_order)

        self.assertEqual("order_abc", update.client_order_id)
        self.assertEqual(tracked_order.current_state, update.new_state)


if __name__ == "__main__":
    unittest.main()
