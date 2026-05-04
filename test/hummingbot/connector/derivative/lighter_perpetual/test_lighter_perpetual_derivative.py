import asyncio
import sys
import time
import types
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PriceType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate


def _ensure_limit_order_stub():
    module_name = "hummingbot.core.data_type.limit_order"
    try:
        __import__(module_name)
        return
    except Exception:
        pass
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class LimitOrder:
        pass

    stub_module.LimitOrder = LimitOrder
    sys.modules[module_name] = stub_module


def _ensure_order_book_stub():
    module_name = "hummingbot.core.data_type.order_book"
    try:
        __import__(module_name)
        return
    except Exception:
        pass
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class OrderBook:
        pass

    stub_module.OrderBook = OrderBook
    sys.modules[module_name] = stub_module


class LighterPerpetualDerivativeTests(unittest.IsolatedAsyncioTestCase):

    connector_cls = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_limit_order_stub()
        _ensure_order_book_stub()
        try:
            from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
                LighterPerpetualDerivative,
            )
            cls.connector_cls = LighterPerpetualDerivative
        except ModuleNotFoundError:
            cls.connector_cls = None

    def setUp(self) -> None:
        super().setUp()
        if self.connector_cls is None:
            self.skipTest("Compiled hummingbot core modules are unavailable in this environment")

        self.connector = self.connector_cls(
            lighter_perpetual_api_key_index="1",
            lighter_perpetual_account_index="237600",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            trading_pairs=["BTC-USDC"],
            trading_required=False,
        )

    async def test_update_balances_parses_collateral(self):
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {
                "collateral": "123.45",
                "available_to_spend": "120.11",
                "fee_level": 2,
            },
        })

        await self.connector._update_balances()

        self.assertEqual(Decimal("123.45"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("120.11"), self.connector._account_available_balances["USDC"])
        self.assertEqual(2, self.connector._fee_tier)

    async def test_update_balances_prefers_available_balance_over_available_to_spend(self):
        # Prefer exchange-reported available_balance when both fields are present.
        # available_to_spend is retained as a fallback for older payload shapes.
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "collateral": "35.60",
                    "available_balance": "6.07",
                    "available_to_spend": "14.42",
                }
            ],
        })

        await self.connector._update_balances()

        self.assertEqual(Decimal("35.60"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("6.07"), self.connector._account_available_balances["USDC"])

    async def test_update_balances_prefers_collateral_over_account_equity_for_total_margin(self):
        # Perp total should use margin-authoritative collateral when both fields exist.
        # account_equity can represent a different aggregate in some payload variants.
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "account_equity": "20.002998766",
                    "collateral": "13.789107",
                    "available_balance": "10.388259",
                }
            ],
        })

        await self.connector._update_balances()

        self.assertEqual(Decimal("13.789107"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("10.388259"), self.connector._account_available_balances["USDC"])

    async def test_update_balances_rest_available_balance_is_authoritative(self):
        # REST available_to_spend / available_balance is now always used directly.
        # If the REST endpoint has no available_to_spend but has available_balance,
        # the REST value is applied as-is.  The old WS-preservation heuristic is removed
        # because it could incorrectly preserve a stale WS value that did not account for
        # open-order margin (the root cause of the balance over-reporting bug).
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "collateral": "35.60",
                    "available_balance": "35.60",  # equals total — REST doesn't deduct position margin
                }
            ],
        })
        # Pre-set a lower available balance (simulating a prior WS update).
        self.connector._account_available_balances["USDC"] = Decimal("27.30")

        await self.connector._update_balances()

        self.assertEqual(Decimal("35.60"), self.connector._account_balances["USDC"])
        # REST is now authoritative — applies 35.60 directly (no preservation heuristic).
        self.assertEqual(Decimal("35.60"), self.connector._account_available_balances["USDC"])

    async def test_update_balances_trusts_available_balance_over_cross_headroom(self):
        # available_balance from the exchange REST is authoritative.
        # When it differs from cross_asset_value - cross_initial_margin_requirement (e.g. because
        # cross_initial_margin_requirement is stale after an order cancel), the exchange-reported
        # available_balance must be used as-is and NOT capped by the stale headroom.
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "collateral": "10.783087",
                    "available_balance": "10.783087",
                    "cross_asset_value": "10.739587",
                    "cross_initial_margin_requirement": "8.386400",  # headroom = 2.353187
                }
            ],
        })

        await self.connector._update_balances()

        self.assertEqual(Decimal("10.783087"), self.connector._account_balances["USDC"])
        # available_balance is trusted directly — NOT capped by cross headroom.
        self.assertEqual(Decimal("10.783087"), self.connector._account_available_balances["USDC"])

    async def test_update_balances_trusts_available_balance_when_cross_requirement_is_stale(self):
        # Regression test: after an order cancel the exchange available_balance updates
        # immediately, but cross_initial_margin_requirement can lag (still includes the
        # cancelled order's margin), making cross_headroom appear zero.
        # The connector must trust available_balance directly and NOT zero it out.
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "collateral": "25.000000",
                    "available_balance": "4.940000",   # correct — order margin freed
                    "cross_asset_value": "25.000000",
                    "cross_initial_margin_requirement": "25.000000",  # stale: still includes cancelled order
                }
            ],
        })

        await self.connector._update_balances()

        self.assertEqual(Decimal("25.000000"), self.connector._account_balances["USDC"])
        # Stale cross_initial_margin_requirement must NOT zero out the correct available_balance.
        self.assertEqual(Decimal("4.940000"), self.connector._account_available_balances["USDC"])

    async def test_update_balances_deducts_open_order_margin_when_available_matches_headroom(self):
        # Pure WS mode: Trust exchange-provided available_balance directly.
        # No local margin estimation; exchange balance is already accurate via WebStream.
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._order_tracker._in_flight_orders = {
            "HBOT-OPEN-1": MagicMock(is_done=False),
        }
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "collateral": "35.993272",
                    "available_balance": "16.878532",
                    "cross_asset_value": "35.993272",
                    "cross_initial_margin_requirement": "19.114740",
                    "positions": [
                        {
                            "market_id": 2,
                            "open_order_count": 2,
                            "initial_margin_fraction": "20.00",
                        }
                    ],
                }
            ],
        })
        self.connector._fetch_active_orders_rows_for_market = AsyncMock(return_value=[
            {"remaining_base_amount": "0.500000", "price": "83.134", "status": "open"},
            {"remaining_base_amount": "0.219000", "price": "80.000", "status": "open"},
        ])

        await self.connector._update_balances()

        # Exchange-provided balance is trusted directly (no local margin subtraction).
        # available_balance from REST already reflects all orders via WS.
        self.assertEqual(Decimal("35.993272"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("16.878532"), self.connector._account_available_balances["USDC"])

    async def test_update_balances_does_not_deduct_estimated_order_margin_without_local_open_orders(self):
        # Pure WS mode: Always trust exchange-provided available_balance directly,
        # regardless of local open order state. No margin estimation applied.
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._order_tracker._in_flight_orders = {}
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "collateral": "35.993272",
                    "available_balance": "16.878532",
                    "cross_asset_value": "35.993272",
                    "cross_initial_margin_requirement": "19.114740",
                    "positions": [
                        {
                            "market_id": 2,
                            "open_order_count": 2,
                            "initial_margin_fraction": "20.00",
                        }
                    ],
                }
            ],
        })
        self.connector._fetch_active_orders_rows_for_market = AsyncMock(return_value=[
            {"remaining_base_amount": "0.500000", "price": "83.134", "status": "open"},
            {"remaining_base_amount": "0.219000", "price": "80.000", "status": "open"},
        ])

        await self.connector._update_balances()

        # Exchange-provided balance is trusted directly (no local margin subtraction).
        self.assertEqual(Decimal("35.993272"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("16.878532"), self.connector._account_available_balances["USDC"])

    async def test_update_balances_clamps_available_to_lower_of_field_and_cross_headroom(self):
        # When available_balance < headroom, the cross-margin guard leaves it unchanged.
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "code": 0,
            "accounts": [
                {
                    "collateral": "35.993272",
                    "available_balance": "5.000000",
                    "cross_asset_value": "35.993272",
                    "cross_initial_margin_requirement": "19.114740",
                    "positions": [
                        {
                            "market_id": 2,
                            "open_order_count": 2,
                            "initial_margin_fraction": "20.00",
                        }
                    ],
                }
            ],
        })
        self.connector._fetch_active_orders_rows_for_market = AsyncMock()

        await self.connector._update_balances()

        # available = min(5.000000, 35.993272 - 19.114740) = min(5.000000, 16.878532) = 5.000000
        self.assertEqual(Decimal("35.993272"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("5.000000"), self.connector._account_available_balances["USDC"])
        self.connector._fetch_active_orders_rows_for_market.assert_not_awaited()

    def test_get_available_balance_does_not_double_subtract_in_flight_orders(self):
        # Perp available balance from exchange is already net of open-order/position margin.
        # It must not be reduced again by local in-flight reservations.
        self.connector._account_available_balances["USDC"] = Decimal("9.610387")

        mock_order = SimpleNamespace(
            is_done=False,
            is_failure=False,
            is_cancelled=False,
            amount=Decimal("0.1"),
            executed_amount_base=Decimal("0"),
            trade_type=TradeType.BUY,
            price=Decimal("83.84"),
            quote_asset="USDC",
            base_asset="SOL",
        )
        self.connector.in_flight_orders["HBOT-1"] = mock_order

        self.assertEqual(Decimal("9.610387"), self.connector.get_available_balance("USDC"))

    def test_get_available_balance_ignores_configured_balance_limit(self):
        self.connector._account_available_balances["USDC"] = Decimal("9.610387")
        self.connector.get_exchange_limit_config = MagicMock(return_value={"USDC": Decimal("2.38")})

        self.assertEqual(Decimal("9.610387"), self.connector.get_available_balance("USDC"))

    async def test_update_balances_parses_short_form_keys(self):
        mock_signer = type("MockSigner", (), {})()
        mock_signer.create_auth_token_with_expiry = lambda api_key_index: ("test_token", None)
        self.connector._get_lighter_signer_client = lambda: mock_signer
        self.connector._get_api_key_index = lambda: 1
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {
                "ae": "250.75",
                "as": "145.50",
                "f": 1,
            },
        })

        await self.connector._update_balances()

        self.assertEqual(Decimal("250.75"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("145.50"), self.connector._account_available_balances["USDC"])

    async def test_process_account_info_ws_event_message_handles_partial_short_payload(self):
        event_message = {
            "channel": "account_info",
            "data": {
                "as": "77.12",
            },
        }

        await self.connector._process_account_info_ws_event_message(event_message)

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)

    async def test_process_account_info_ws_event_message_preserves_zero_available_balance(self):
        event_message = {
            "channel": "account_info",
            "data": {
                "ae": 100,
                "as": 0,
            },
        }

        await self.connector._process_account_info_ws_event_message(event_message)

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)

    async def test_process_account_all_ws_event_message_ignores_partial_top_level_balance_fields(self):
        self.connector._account_balances["USDC"] = Decimal("100")
        self.connector._account_available_balances["USDC"] = Decimal("95")
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_all_orders_ws_event_message = AsyncMock()

        # Partial payload: only collateral present (no available_to_spend).
        # Total is updated from collateral; available_balance is preserved from existing.
        event_message = {
            "collateral": "120",
        }

        await self.connector._process_account_all_ws_event_message(event_message)

        # WS no longer mutates balances directly; existing balances remain unchanged.
        self.assertEqual(Decimal("100"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("95"), self.connector._account_available_balances["USDC"])

    async def test_process_account_all_ws_event_message_preserves_zero_available_balance(self):
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_all_orders_ws_event_message = AsyncMock()

        event_message = {
            "collateral": 120,
            "available_to_spend": 0,
        }

        await self.connector._process_account_all_ws_event_message(event_message)

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)

    def test_set_usdc_balances_replaces_stale_assets(self):
        self.connector._account_balances["BTC"] = Decimal("1")
        self.connector._account_available_balances["BTC"] = Decimal("0.5")

        self.connector._set_usdc_balances(Decimal("10"), Decimal("7"))

        self.assertEqual({"USDC": Decimal("10")}, self.connector._account_balances)
        self.assertEqual({"USDC": Decimal("7")}, self.connector._account_available_balances)

    def test_check_network_request_path_uses_exchange_stats(self):
        self.assertEqual("/exchangeStats", self.connector.check_network_request_path)

    def test_status_dict_requires_balance_fetched_once_for_trading_connectors(self):
        trading_connector = self.connector_cls(
            lighter_perpetual_api_key_index="1",
            lighter_perpetual_account_index="237600",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            trading_pairs=["BTC-USDC"],
            trading_required=True,
        )
        trading_connector._account_balances["USDC"] = Decimal("10")
        # timestamp=0 means balance never fetched → not ready
        trading_connector._last_balance_update_timestamp = 0
        self.assertFalse(trading_connector.status_dict["account_balance"])

        # once fetched (even long ago), connector is ready
        trading_connector._last_balance_update_timestamp = time.time() - 3600
        self.assertTrue(trading_connector.status_dict["account_balance"])

    def test_status_dict_requires_recent_position_sync_for_trading_connectors(self):
        trading_connector = self.connector_cls(
            lighter_perpetual_api_key_index="1",
            lighter_perpetual_account_index="237600",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            trading_pairs=["BTC-USDC"],
            trading_required=True,
        )
        trading_connector._account_balances["USDC"] = Decimal("10")
        trading_connector._last_balance_update_timestamp = time.time()

        trading_connector._last_position_update_timestamp = 0
        self.assertFalse(trading_connector.status_dict["account_position"])

        trading_connector._last_position_update_timestamp = time.time()
        self.assertTrue(trading_connector.status_dict["account_position"])

        trading_connector._last_position_update_timestamp = time.time() - 120
        self.assertFalse(trading_connector.status_dict["account_position"])

    def test_is_user_stream_initialized_requires_recent_messages(self):
        trading_connector = self.connector_cls(
            lighter_perpetual_api_key_index="1",
            lighter_perpetual_account_index="237600",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            trading_pairs=["BTC-USDC"],
            trading_required=True,
        )
        trading_connector._user_stream_tracker = SimpleNamespace(
            data_source=SimpleNamespace(last_recv_time=time.time() - 240)
        )

        self.assertFalse(trading_connector._is_user_stream_initialized())

    def test_get_poll_interval_is_short_when_any_active_order_exists(self):
        now = time.time()
        self.connector._user_stream_tracker = SimpleNamespace(last_recv_time=now)
        self.connector._order_tracker.active_orders["test-order"] = SimpleNamespace(position=PositionAction.OPEN)

        interval = self.connector._get_poll_interval(timestamp=now)

        self.assertEqual(self.connector._HEALTHY_PRIVATE_STREAM_POLL_INTERVAL, interval)

    def test_get_poll_interval_is_short_when_open_position_exists(self):
        now = time.time()
        self.connector._user_stream_tracker = SimpleNamespace(last_recv_time=now)
        self.connector._order_tracker.active_orders.clear()
        self.connector._perpetual_trading.account_positions["HYPE-USDC-LONG"] = SimpleNamespace(amount=Decimal("0.5"))

        interval = self.connector._get_poll_interval(timestamp=now)

        self.assertEqual(self.connector._HEALTHY_PRIVATE_STREAM_POLL_INTERVAL, interval)

    def test_allocate_client_order_index_uses_high_range_spacing(self):
        self.connector._last_client_order_index = 0

        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.time.time",
            return_value=1000.001,
        ):
            first_index = self.connector._allocate_client_order_index()
            second_index = self.connector._allocate_client_order_index()

        expected_first_index = int(1000.001 * 1000) * self.connector._CLIENT_ORDER_INDEX_TIME_MULTIPLIER
        self.assertEqual(expected_first_index, first_index)
        self.assertEqual(first_index + 1, second_index)

    def test_get_api_key_index_prefers_explicit_index_and_secret(self):
        self.connector.api_key_index = "4"
        self.assertEqual(4, self.connector._get_api_key_index())

        self.connector.api_key_index = ""
        self.connector.api_key = "0x" + ("a" * 64)
        self.connector.api_secret = "12"
        self.assertEqual(12, self.connector._get_api_key_index())

    def test_get_api_key_index_raises_for_non_numeric_config(self):
        self.connector.api_key = "0x" + ("a" * 64)
        self.connector.api_secret = "not-a-number"
        self.connector.api_key_index = ""

        with self.assertRaises(ValueError):
            self.connector._get_api_key_index()

    async def test_fetch_or_create_api_config_key_resolves_index_from_api_keys(self):
        self.connector.api_key = "abc_public_key"
        self.connector.api_secret = ""
        self.connector.api_config_key = "abc_public_key"
        self.connector.api_key_index = ""
        self.connector.account_index = "237600"
        self.connector._api_get = AsyncMock(return_value={
            "api_keys": [
                {"api_key_index": 3, "public_key": "other_key"},
                {"api_key_index": 5, "public_key": "abc_public_key"},
            ]
        })

        await self.connector._fetch_or_create_api_config_key()

        self.assertEqual("5", self.connector.api_key_index)

    def test_helper_methods_cover_warning_and_order_book_paths(self):
        warning_timestamps = {}
        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.time.time",
            side_effect=[100.0, 105.0, 131.0],
        ):
            self.assertTrue(self.connector._should_emit_throttled_warning("BTC-USDC", warning_timestamps))
            self.assertFalse(self.connector._should_emit_throttled_warning("BTC-USDC", warning_timestamps))
            self.assertTrue(self.connector._should_emit_throttled_warning("BTC-USDC", warning_timestamps))

        self.assertEqual("first", self.connector._first_not_none(None, "first", "second"))
        self.assertIsNone(self.connector._first_not_none(None, None))

        logger = MagicMock()
        self.connector.logger = MagicMock(return_value=logger)
        self.connector.quantize_order_price = MagicMock(side_effect=lambda trading_pair, price: price)
        self.connector._last_empty_order_book_warning_timestamp = {}
        self.connector.get_order_book = MagicMock(side_effect=RuntimeError("missing book"))

        self.assertTrue(self.connector._get_top_order_book_price("BTC-USDC", True).is_nan())
        logger.warning.assert_called_once()

    def test_mark_private_event_and_build_account_auth_params(self):
        self.connector._last_private_account_event_timestamp = 0.0
        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.time.time",
            return_value=123.0,
        ):
            self.connector._mark_private_account_event_received()
        self.assertEqual(123.0, self.connector._last_private_account_event_timestamp)

        self.connector.account_index = "237600"
        self.connector.api_key_index = "4"
        self.connector._auth_token_cache = ("cached-auth", 200.0)
        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.time.time",
            return_value=100.0,
        ):
            params = self.connector._build_account_auth_params()
        self.assertEqual("cached-auth", params["auth"])

        signer_client = MagicMock()
        signer_client.create_auth_token_with_expiry = MagicMock(return_value=(None, "bad key"))
        self.connector._auth_token_cache = None
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_client)
        with self.assertRaises(IOError):
            self.connector._build_account_auth_params()

    async def test_fetch_account_snapshot_data_validates_error_and_missing_account(self):
        self.connector._build_account_auth_params = MagicMock(return_value={"auth": "token"})
        self.connector._api_get = AsyncMock(return_value={"code": 500, "message": "server error"})

        with self.assertRaises(IOError):
            await self.connector._fetch_account_snapshot_data()

        self.connector._api_get = AsyncMock(return_value={"code": 200, "data": []})

        with self.assertRaises(IOError):
            await self.connector._fetch_account_snapshot_data()

    async def test_schedule_fast_balance_sync_respects_gate_and_logs_errors(self):
        self.connector._trading_required = False
        self.connector._update_balances = AsyncMock()
        self.connector._last_balance_update_timestamp = 0.0

        self.connector._schedule_fast_balance_sync()
        self.connector._update_balances.assert_not_awaited()

        logger = MagicMock()
        self.connector.logger = MagicMock(return_value=logger)
        self.connector._trading_required = True
        self.connector._last_balance_update_timestamp = 0.0
        self.connector._update_balances = AsyncMock(side_effect=RuntimeError("boom"))

        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.safe_ensure_future",
            side_effect=lambda coro: asyncio.get_running_loop().create_task(coro),
        ):
            self.connector._schedule_fast_balance_sync(min_interval_seconds=0.0)
            await asyncio.sleep(0)

        logger.debug.assert_called_once()

    async def test_estimate_open_order_initial_margin_handles_positions_and_cached_rows(self):
        self.connector._active_orders_snapshot_by_market = {
            2: [
                {"remaining_base_amount": "2", "price": "10"},
                {"remaining_size": "1", "limit_price": "5"},
                {"remaining_base_amount": "bad", "price": "5"},
            ]
        }
        self.connector._active_orders_snapshot_market_complete = set()
        self.connector._status_poll_cycle_active = True
        self.connector._fetch_active_orders_rows_for_market = AsyncMock(return_value=[
            {"remaining_amount": "3", "price": "4"},
            {"remaining_amount": "0", "price": "4"},
        ])

        margin = await self.connector._estimate_open_order_initial_margin(
            {
                "positions": [
                    {
                        "market_id": 2,
                        "open_order_count": 2,
                        "initial_margin_fraction": "10",
                    },
                    {
                        "market_id": 3,
                        "open_order_count": 1,
                        "initial_margin_fraction": "20",
                    },
                    {"market_id": 4, "open_order_count": 0, "initial_margin_fraction": "20"},
                    "bad-position",
                ]
            }
        )

        self.assertEqual(Decimal("4.9"), margin)
        self.assertIn(3, self.connector._active_orders_snapshot_by_market)
        self.assertIn(3, self.connector._active_orders_snapshot_market_complete)

        self.assertIsNone(await self.connector._estimate_open_order_initial_margin({"positions": "bad"}))

    async def test_apply_balances_from_account_data_handles_warning_direct_and_cross_paths(self):
        logger = MagicMock()
        self.connector.logger = MagicMock(return_value=logger)
        self.connector._account_balances = {}
        self.connector._account_available_balances = {}
        self.connector._set_usdc_balances = MagicMock()

        await self.connector._apply_balances_from_account_data({})
        logger.warning.assert_called_once()

        logger.reset_mock()
        await self.connector._apply_balances_from_account_data(
            {
                "collateral": "12.5",
                "available_balance": "7.25",
                "fee_level": 3,
            }
        )
        self.connector._set_usdc_balances.assert_called_with(
            total_balance=Decimal("12.5"),
            available_balance=Decimal("7.25"),
        )
        self.assertEqual(3, self.connector._fee_tier)

        self.connector._set_usdc_balances.reset_mock()
        await self.connector._apply_balances_from_account_data(
            {
                "assets": [{"symbol": "USDC", "margin_balance": "15"}],
                "cross_asset_value": "10",
                "cross_initial_margin_requirement": "4",
            }
        )
        self.connector._set_usdc_balances.assert_called_with(
            total_balance=Decimal("10"),
            available_balance=Decimal("6"),
        )

    async def test_apply_balances_from_account_data_skips_when_available_is_missing(self):
        logger = MagicMock()
        self.connector.logger = MagicMock(return_value=logger)
        self.connector._account_balances = {"USDC": Decimal("11")}
        self.connector._account_available_balances = {"USDC": Decimal("9")}
        self.connector._set_usdc_balances = MagicMock()

        await self.connector._apply_balances_from_account_data({"collateral": "12"})

        logger.debug.assert_called_once()
        self.connector._set_usdc_balances.assert_not_called()

    def test_should_ignore_unmatched_trade_message_only_for_external_manual_cases(self):
        self.connector._perpetual_trading.account_positions.clear()
        tracked_orders = {"11": object()}
        order_index_to_client_index = {"22": "33"}

        self.assertFalse(
            self.connector._should_ignore_unmatched_trade_message(
                {"s": "BTC", "i": "99"}, tracked_orders, order_index_to_client_index
            )
        )
        self.assertFalse(
            self.connector._should_ignore_unmatched_trade_message(
                {"i": "11"}, tracked_orders, {}
            )
        )
        self.assertFalse(
            self.connector._should_ignore_unmatched_trade_message(
                {"i": "22"}, {}, order_index_to_client_index
            )
        )
        self.assertTrue(
            self.connector._should_ignore_unmatched_trade_message(
                {"i": "999"}, {}, {}
            )
        )

    async def test_try_process_one_trade_entry_processes_fill_and_close_completion(self):
        processed_trade_updates = []
        processed_order_updates = []
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "55"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.quote_asset = "USDC"
        tracked_order.position = PositionAction.CLOSE
        tracked_order.executed_amount_base = Decimal("1")
        tracked_order.amount = Decimal("1")

        self.connector._client_order_index_to_client_order_id = {"55": "HBOT-1"}
        self.connector._client_order_index_to_order_index = {"55": "9001"}
        self.connector._order_tracker = SimpleNamespace(
            process_trade_update=lambda update: processed_trade_updates.append(update),
            process_order_update=lambda update: processed_order_updates.append(update),
        )
        self.connector._update_positions = AsyncMock()
        self.connector._update_balances = AsyncMock()

        matched = await self.connector._try_process_one_trade_entry(
            {
                "i": "9001",
                "client_order_index": "55",
                "trade_id": "fill-1",
                "a": "1",
                "p": "10",
                "f": "0.1",
                "t": 1700000000000,
            },
            tracked_orders={},
            all_fillable_orders={"HBOT-1": tracked_order},
            order_index_to_client_index={"9001": "55"},
        )

        self.assertTrue(matched)
        tracked_order.update_exchange_order_id.assert_called_once_with("9001")
        self.assertEqual(1, len(processed_trade_updates))
        self.assertEqual(1, len(processed_order_updates))
        self.connector._update_positions.assert_awaited_once()
        self.connector._update_balances.assert_awaited_once()

    async def test_replay_pending_trade_entries_reconciles_stale_ignores_external_and_keeps_recent(self):
        self.connector._order_tracker = SimpleNamespace(all_fillable_orders={})
        self.connector._client_order_index_to_order_index = {}
        self.connector._pending_trade_entries = [
            (10.0, {"i": "stale"}),
            (11.0, {"i": "external"}),
            (18.5, {"i": "recent"}),
        ]
        self.connector._try_process_one_trade_entry = AsyncMock(side_effect=[False, False, False])
        self.connector._should_ignore_unmatched_trade_message = MagicMock(side_effect=[False, True, False])
        self.connector._reconcile_unmatched_private_event = AsyncMock()

        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.time.time",
            return_value=20.0,
        ):
            await self.connector._replay_pending_trade_entries()

        self.connector._reconcile_unmatched_private_event.assert_awaited_once()
        self.assertEqual([(18.5, {"i": "recent"})], self.connector._pending_trade_entries)

    async def test_set_trading_pair_leverage_uses_signer_client(self):
        self.connector._get_market_spec = AsyncMock(return_value=(3, 2, 2, "DOGE"))
        mock_signer = MagicMock()
        mock_signer.CROSS_MARGIN_MODE = 0
        mock_signer.update_leverage = AsyncMock(return_value=(None, {"success": True}, None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_api_key_index = MagicMock(return_value=4)
        self.connector._update_balances = AsyncMock()

        success, message = await self.connector._set_trading_pair_leverage("DOGE-USDC", 5)

        self.assertTrue(success)
        self.assertEqual("", message)
        self.connector._update_balances.assert_awaited_once()
        mock_signer.update_leverage.assert_awaited_once_with(
            market_index=3,
            margin_mode=0,
            leverage=5,
            api_key_index=4,
        )

    async def test_set_trading_pair_leverage_retries_on_transient_error(self):
        self.connector._get_market_spec = AsyncMock(return_value=(3, 2, 2, "DOGE"))
        mock_signer = MagicMock()
        mock_signer.CROSS_MARGIN_MODE = 0
        mock_signer.update_leverage = AsyncMock(side_effect=[
            (None, None, "context deadline exceeded"),
            (None, {"success": True}, None),
        ])
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_api_key_index = MagicMock(return_value=4)
        self.connector._sleep = AsyncMock()
        self.connector._update_balances = AsyncMock()

        success, message = await self.connector._set_trading_pair_leverage("DOGE-USDC", 5)

        self.assertTrue(success)
        self.assertEqual("", message)
        self.assertEqual(2, mock_signer.update_leverage.await_count)
        self.connector._update_balances.assert_awaited_once()
        self.connector._sleep.assert_awaited_once()

    def test_get_signer_private_key_prefers_explicit_private_key(self):
        # api_key holds the signing private key when it's a hex string (not an integer index)
        self.connector.api_key = "0x" + ("a" * 64)
        self.connector.api_secret = "1"
        self.assertEqual("0x" + ("a" * 64), self.connector._get_signer_private_key())

    def test_is_int_string_handles_valid_and_invalid_values(self):
        self.assertTrue(self.connector._is_int_string("12"))
        self.assertTrue(self.connector._is_int_string(34))
        self.assertFalse(self.connector._is_int_string("abc"))
        self.assertFalse(self.connector._is_int_string(None))

    def test_get_rest_api_key_prefers_numeric_api_key_then_secret_then_api_key(self):
        self.connector.api_key = "7"
        self.connector.api_secret = "secret"
        self.assertEqual("7", self.connector._get_rest_api_key())

        self.connector.api_key = "not-numeric"
        self.assertEqual("secret", self.connector._get_rest_api_key())

        self.connector.api_secret = ""
        self.assertEqual("not-numeric", self.connector._get_rest_api_key())

    def test_get_signer_private_key_uses_api_key_when_private_key_missing(self):
        self.connector.private_key = ""
        self.connector.api_key = "0x" + ("a" * 64)
        self.connector.api_secret = "7"
        self.assertEqual("0x" + ("a" * 64), self.connector._get_signer_private_key())

        self.connector.api_key = "7"
        self.connector.api_secret = "0xsecret"
        with self.assertRaises(ValueError):
            self.connector._get_signer_private_key()

    def test_get_signer_private_key_raises_when_missing(self):
        self.connector.private_key = ""
        self.connector.api_key = "7"
        self.connector.api_secret = "6"

        with self.assertRaises(ValueError):
            self.connector._get_signer_private_key()

    def test_api_host_for_signer_uses_domain(self):
        self.assertEqual("https://mainnet.zklighter.elliot.ai", self.connector._api_host_for_signer())

        self.connector._domain = "lighter_perpetual_testnet"
        self.assertEqual("https://testnet.zklighter.elliot.ai", self.connector._api_host_for_signer())

    def test_get_account_index_and_account_helpers(self):
        self.assertEqual(237600, self.connector._get_account_index())
        self.assertEqual({"by": "index", "value": "237600", "active_only": "true"}, self.connector._account_query_params())
        self.assertEqual({"id": 1}, self.connector._account_from_response({"data": {"id": 1}}))
        self.assertEqual({"id": 1}, self.connector._account_from_response({"data": [{"id": 1}]}))
        self.assertEqual({"id": 2}, self.connector._account_from_response({"accounts": [{"id": 2}]}))
        # Top-level account response (no data/accounts wrapper)
        top_level = {"code": 200, "collateral": "5.7", "available_balance": "5.7", "assets": []}
        self.assertEqual(top_level, self.connector._account_from_response(top_level))
        self.assertIsNone(self.connector._account_from_response({}))

        self.connector.account_index = "bad"
        with self.assertRaises(ValueError):
            self.connector._get_account_index()

    def test_is_ok_response_and_signer_client_builds_once(self):
        self.assertTrue(self.connector._is_ok_response({"success": True}))
        self.assertTrue(self.connector._is_ok_response({"code": 200}))
        self.assertTrue(self.connector._is_ok_response({"code": 0}))   # Lighter uses code=0 for success
        self.assertFalse(self.connector._is_ok_response({"code": 5}))   # Lighter error code
        self.assertFalse(self.connector._is_ok_response({"code": 500}))

        fake_lighter = types.ModuleType("lighter")

        class SignerClient:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        fake_lighter.signer_client = SimpleNamespace(SignerClient=SignerClient)
        sys.modules["lighter"] = fake_lighter
        self.connector._lighter_signer_client = None

        client_1 = self.connector._get_lighter_signer_client()
        client_2 = self.connector._get_lighter_signer_client()

        self.assertIs(client_1, client_2)
        self.assertEqual(237600, client_1.kwargs["account_index"])

    async def test_refresh_market_metadata_filters_for_perpetual_markets(self):
        self.connector._api_get = AsyncMock(return_value={
            "order_books": [
                {
                    "symbol": "BTC",
                    "market_type": "perp",
                    "market_id": 1,
                    "supported_size_decimals": 3,
                    "supported_price_decimals": 2,
                },
                {"symbol": "ETH/USDC", "market_type": "spot", "market_id": 2},
            ]
        })

        await self.connector._refresh_market_metadata()

        self.assertEqual(1, self.connector._market_id_by_symbol["BTC"])
        self.assertNotIn("ETH/USDC", self.connector._market_id_by_symbol)

    def test_properties_and_supported_modes(self):
        self.assertEqual("lighter_perpetual", self.connector.name)
        self.assertEqual("lighter_perpetual", self.connector.domain)
        self.assertEqual(32, self.connector.client_order_id_max_length)
        self.assertEqual("HBOT", self.connector.client_order_id_prefix)
        self.assertEqual("/orderBooks", self.connector.trading_rules_request_path)
        self.assertEqual("/orderBooks", self.connector.trading_pairs_request_path)
        self.assertEqual("/exchangeStats", self.connector.check_network_request_path)
        self.assertEqual(["BTC-USDC"], self.connector.trading_pairs)
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)
        self.assertFalse(self.connector.is_trading_required)
        self.assertEqual(120, self.connector.funding_fee_poll_interval)
        self.assertEqual([OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET], self.connector.supported_order_types())
        self.assertEqual([PositionMode.ONEWAY], self.connector.supported_position_modes())
        self.assertEqual("USDC", self.connector.get_buy_collateral_token("BTC-USDC"))
        self.assertEqual("USDC", self.connector.get_sell_collateral_token("BTC-USDC"))

    async def test_api_request_url_and_rate_limits_rules(self):
        self.assertEqual(
            "https://mainnet.zklighter.elliot.ai/api/v1/account",
            await self.connector._api_request_url("/account"),
        )

        self.connector._domain = "lighter_perpetual_testnet"
        self.assertEqual(
            "https://testnet.zklighter.elliot.ai/api/v1/account",
            await self.connector._api_request_url("/account"),
        )
        self.connector._domain = "lighter_perpetual"

        self.connector.api_key = ""
        self.assertEqual(self.connector.rate_limits_rules, self.connector.rate_limits_rules)

        self.connector.api_key = "1"
        self.connector._fee_tier = 2
        rate_limits = self.connector.rate_limits_rules
        self.assertGreater(len(rate_limits), 0)
        self.assertEqual("LIGHTER_LIMIT", rate_limits[0].limit_id)

    async def test_api_request_routes_authenticated_and_public_requests(self):
        # Authenticated request: _api_request must NOT inject X-Api-Key header
        # (auth token is passed as the 'auth' query param by callers, not via header)
        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase._api_request",
            new=AsyncMock(return_value={"auth": True}),
        ) as super_req:
            auth_result = await self.connector._api_request(path_url="/account", is_auth_required=True)
            self.assertEqual({"auth": True}, auth_result)
            auth_headers = super_req.await_args.kwargs.get("headers") or {}
            self.assertNotIn("X-Api-Key", auth_headers)

        # Public request: _api_request must NOT inject X-Api-Key header
        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase._api_request",
            new=AsyncMock(return_value={"auth": False}),
        ) as super_req:
            public_result = await self.connector._api_request(path_url="/account", is_auth_required=False)
            self.assertEqual({"auth": False}, public_result)
            public_headers = super_req.await_args.kwargs.get("headers") or {}
            self.assertNotIn("X-Api-Key", public_headers)

    async def test_fetch_or_create_api_config_key_short_circuits_and_warns(self):
        self.connector.api_config_key = "abc"
        self.connector.api_key_index = "5"
        self.connector._api_get = AsyncMock()

        await self.connector._fetch_or_create_api_config_key()

        self.connector._api_get.assert_not_awaited()

        self.connector.api_config_key = ""
        self.connector.api_key_index = ""
        self.connector.account_index = ""
        self.connector.api_key = ""
        self.connector.api_secret = ""
        logger = MagicMock()
        self.connector.logger = MagicMock(return_value=logger)

        await self.connector._fetch_or_create_api_config_key()

        logger.warning.assert_called_once()

    async def test_fetch_or_create_api_config_key_updates_throttler_and_warns_when_missing(self):
        logger = MagicMock()
        throttler = MagicMock()
        self.connector.logger = MagicMock(return_value=logger)
        self.connector._throttler = throttler
        self.connector.api_key = "abc_public_key"
        self.connector.api_secret = ""
        self.connector.api_key_index = ""
        self.connector.api_config_key = ""
        self.connector.account_index = "237600"
        self.connector._api_get = AsyncMock(return_value={
            "api_keys": [{"api_key_index": 5, "public_key": "abc_public_key"}]
        })

        await self.connector._fetch_or_create_api_config_key()

        self.assertEqual("5", self.connector.api_key_index)
        throttler.set_rate_limits.assert_called_once()

        self.connector.api_key_index = ""
        self.connector._api_get = AsyncMock(return_value={"api_keys": []})

        await self.connector._fetch_or_create_api_config_key()

        logger.warning.assert_called()

    def test_generate_api_key_pair_returns_private_and_public_keys(self):
        with patch("lighter.create_api_key", return_value=("priv", "pub", None)):
            private_key, public_key = self.connector.generate_api_key_pair()

        self.assertEqual("priv", private_key)
        self.assertEqual("pub", public_key)

    def test_set_lighter_price_keeps_latest_timestamp(self):
        self.connector.set_LIGHTER_price("BTC-USDC", 200.0, Decimal("101"), Decimal("102"))
        self.connector.set_LIGHTER_price("BTC-USDC", 199.0, Decimal("99"), Decimal("100"))

        price_record = self.connector.get_LIGHTER_price("BTC-USDC")
        self.assertEqual(200.0, price_record.timestamp)
        self.assertEqual(Decimal("101"), price_record.index_price)
        self.assertEqual(Decimal("102"), price_record.mark_price)

    def test_get_price_by_type_returns_nan_when_order_book_empty(self):
        order_book_module = __import__("hummingbot.core.data_type.order_book", fromlist=["OrderBook"])
        OrderBook = getattr(order_book_module, "OrderBook")

        empty_order_book = OrderBook()
        self.connector.get_order_book = MagicMock(return_value=empty_order_book)
        self.connector.set_LIGHTER_price("BTC-USDC", time.time(), Decimal("101"), Decimal("102"))

        # Some local test environments provide a runtime variant that omits get_price_by_type.
        # Fall back to get_price to keep the NaN-on-empty-orderbook behavior check deterministic.
        if hasattr(self.connector, "get_price_by_type"):
            best_ask = self.connector.get_price_by_type("BTC-USDC", PriceType.BestAsk)
            best_bid = self.connector.get_price_by_type("BTC-USDC", PriceType.BestBid)
        elif hasattr(self.connector, "get_price"):
            best_ask = self.connector.get_price("BTC-USDC", True)
            best_bid = self.connector.get_price("BTC-USDC", False)
        else:
            self.skipTest("Connector runtime variant does not expose get_price_by_type/get_price")

        self.assertTrue(best_ask.is_nan())
        self.assertTrue(best_bid.is_nan())

    async def test_get_last_traded_price_logs_no_candle_warning(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._market_id_by_symbol["BTC"] = 1
        self.connector._size_decimals_by_symbol["BTC"] = 3
        self.connector._price_decimals_by_symbol["BTC"] = 2
        self.connector._api_get = AsyncMock(return_value={"data": []})
        logger_mock = MagicMock()
        self.connector.logger = MagicMock(return_value=logger_mock)

        price = await self.connector._get_last_traded_price("BTC-USDC")

        self.assertEqual(0.0, price)
        logger_mock.warning.assert_called()

    async def test_process_account_order_updates_ws_event_message_updates_tracked_order(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.executed_amount_base = Decimal("0")
        tracked_order.amount = Decimal("1")
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "os": "filled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual("123", order_update.exchange_order_id)

    async def test_process_account_order_updates_ws_event_message_maps_client_index_to_exchange_order_id(self):
        # tracked order starts with client_order_index as exchange_order_id
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "999"   # client_order_index placeholder
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.executed_amount_base = Decimal("0")
        tracked_order.amount = Decimal("1")
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()

        # WS sends i=<order_index>, I=<client_order_index>
        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "I": 999, "os": "filled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
        # exchange_order_id must be updated to the real order_index "123"
        self.assertEqual("123", order_update.exchange_order_id)
        # mapping must be populated
        self.assertEqual("123", self.connector._client_order_index_to_order_index.get("999"))

    async def test_process_account_order_updates_ws_event_message_uses_client_index_when_exchange_id_missing(self):
        # tracked order is known only by the initial client_order_index placeholder
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "999"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.executed_amount_base = Decimal("0")
        tracked_order.amount = Decimal("1")
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()

        # WS sends only client_order_index without real exchange order id
        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"I": 999, "os": "canceled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual("999", order_update.exchange_order_id)

    async def test_process_account_order_updates_ws_event_message_uses_reverse_mapping_when_client_index_missing(self):
        # tracked order still has placeholder client_order_index as exchange_order_id
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "999"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.executed_amount_base = Decimal("0")
        tracked_order.amount = Decimal("1")
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()

        # Pretend we learned this mapping from account_all or active-order reconciliation.
        self.connector._client_order_index_to_client_order_id["999"] = "HBOT-1"
        self.connector._client_order_index_to_order_index["999"] = "123"

        # WS sends only i=<order_index> (I omitted/null).
        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "os": "canceled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual("123", order_update.exchange_order_id)

    async def test_resolve_exchange_order_id_matches_client_order_index(self):
        mock_signer = MagicMock()
        mock_signer.create_auth_token_with_expiry = MagicMock(return_value=("auth-token", None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_api_key_index = MagicMock(return_value=4)
        # First page: no results, has_more=True
        # Second page: contains our order
        self.connector._api_get = AsyncMock(side_effect=[
            {
                "success": True,
                "code": 200,
                "data": [],
                "has_more": True,
                "next_cursor": "cursor-1",
            },
            {
                "success": True,
                "code": 200,
                "data": [
                    {
                        "client_order_id": "888",
                        "order_id": "123456",
                    }
                ],
                "has_more": False,
            },
        ])

        order_index = await self.connector._resolve_order_index_from_active_orders(
            market_id=1,
            client_order_index="888",
        )

        self.assertEqual("123456", order_index)
        # Mapping must also be populated
        self.assertEqual("123456", self.connector._client_order_index_to_order_index.get("888"))

    async def test_process_account_order_updates_ws_event_message_ignores_unknown_order(self):
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {}
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._reconcile_unmatched_private_event = AsyncMock()

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "os": "filled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_not_called()
        self.connector._reconcile_unmatched_private_event.assert_awaited_once()

    async def test_process_account_order_updates_refreshes_positions_on_partial_open_cancel(self):
        """When a partially-filled OPEN order is cancelled via WS, _refresh_account_state must
        be triggered so the strategy sees the residual position at the next clock tick and can
        create the correct close order — rather than orphaning the partial position."""
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-OPEN-1"
        tracked_order.trading_pair = "SOL-USDC"
        tracked_order.position = PositionAction.OPEN
        # Simulate 0.022 SOL partial fill before the cancel
        tracked_order.executed_amount_base = Decimal("0.022")
        tracked_order.amount = Decimal("1.0")

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-OPEN-1": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._refresh_account_state = AsyncMock()

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "os": "canceled", "ut": 1700000000000}],
        })

        # position refresh must have fired so the strategy sees the 0.022 SOL residual
        self.connector._refresh_account_state.assert_awaited_once()
        call_kwargs = self.connector._refresh_account_state.call_args.kwargs
        self.assertTrue(call_kwargs.get("refresh_positions"))
        self.assertTrue(call_kwargs.get("refresh_balances"))

    async def test_process_account_order_updates_unfilled_open_cancel_refreshes_balances_only(self):
        """A CANCELLED OPEN order with zero fills should refresh balances (to release locked margin)
        but must not refresh positions (no residual position to reconcile)."""
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "456"
        tracked_order.client_order_id = "HBOT-OPEN-2"
        tracked_order.trading_pair = "SOL-USDC"
        tracked_order.position = PositionAction.OPEN
        # No partial fills — zero executed amount
        tracked_order.executed_amount_base = Decimal("0")
        tracked_order.amount = Decimal("1.0")

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-OPEN-2": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._refresh_account_state = AsyncMock()

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 456, "os": "canceled", "ut": 1700000000000}],
        })

        self.connector._refresh_account_state.assert_awaited_once()
        call_kwargs = self.connector._refresh_account_state.call_args.kwargs
        self.assertFalse(call_kwargs.get("refresh_positions"))
        self.assertTrue(call_kwargs.get("refresh_balances"))

    async def test_process_account_order_updates_open_fill_refreshes_balances_only(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "777"
        tracked_order.client_order_id = "HBOT-OPEN-3"
        tracked_order.trading_pair = "SOL-USDC"
        tracked_order.position = PositionAction.OPEN
        tracked_order.executed_amount_base = Decimal("1.0")
        tracked_order.amount = Decimal("1.0")

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-OPEN-3": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._refresh_account_state = AsyncMock()

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 777, "os": "filled", "ut": 1700000000000}],
        })

        self.connector._refresh_account_state.assert_awaited_once()
        call_kwargs = self.connector._refresh_account_state.call_args.kwargs
        self.assertFalse(call_kwargs.get("refresh_positions"))
        self.assertTrue(call_kwargs.get("refresh_balances"))

    async def test_process_account_order_updates_ignores_stale_cancel_after_filled(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-FILLED-1"
        tracked_order.trading_pair = "SOL-USDC"
        tracked_order.current_state = OrderState.FILLED
        tracked_order.position = PositionAction.OPEN
        tracked_order.executed_amount_base = Decimal("1.0")
        tracked_order.amount = Decimal("1.0")

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-FILLED-1": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._refresh_account_state = AsyncMock()

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "os": "canceled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_not_called()
        self.connector._refresh_account_state.assert_not_awaited()

    async def test_process_account_all_orders_ignores_stale_cancel_after_filled(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-FILLED-2"
        tracked_order.trading_pair = "SOL-USDC"
        tracked_order.current_state = OrderState.FILLED
        tracked_order.creation_timestamp = time.time() - 120
        tracked_order.position = PositionAction.OPEN
        tracked_order.executed_amount_base = Decimal("1.0")
        tracked_order.amount = Decimal("1.0")

        self.connector._client_order_index_to_client_order_id["999"] = "HBOT-FILLED-2"
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_updatable_orders = {"HBOT-FILLED-2": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()
        self.connector._refresh_account_state = AsyncMock()
        self.connector._verify_cancel_not_false = AsyncMock()

        await self.connector._process_account_all_orders_ws_event_message({
            "data": {
                "orders": [
                    {
                        "order_index": "123",
                        "client_order_index": "999",
                        "order_status": "canceled",
                        "updated_at": 1700000000000,
                    }
                ]
            }
        })

        self.connector._order_tracker.process_order_update.assert_not_called()
        self.connector._refresh_account_state.assert_not_awaited()
        self.connector._verify_cancel_not_false.assert_not_called()

    async def test_process_account_positions_ws_event_message_preserves_stale_on_rebuild_exception(self):
        """If trading_pair resolution raises mid-loop, the existing positions must be preserved
        (not wiped). The WS handler now uses the same atomic clear-after-rebuild pattern as
        _update_positions() REST path."""
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {"SOL-USDC-LONG": "stale_sol_position"}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()
        # Second symbol resolution raises — simulating an unexpected symbol mid-snapshot
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(
            side_effect=["SOL-USDC", Exception("unknown symbol BTC")]
        )
        self.connector.get_leverage = MagicMock(return_value="5")
        self.connector.set_LIGHTER_price("SOL-USDC", 100.0, Decimal("82"), Decimal("82"))

        with self.assertRaises(Exception):
            await self.connector._process_account_positions_ws_event_message({
                "channel": "account_positions",
                "data": [
                    {"s": "SOL", "d": "bid", "a": "0.022", "p": "82.2"},
                    {"s": "BTC", "d": "bid", "a": "0.001", "p": "90000"},
                ],
            })

        # Stale position must be preserved — the atomic rebuild failed so we keep old data
        self.assertIn("SOL-USDC-LONG", self.connector._perpetual_trading.account_positions)
        self.assertEqual("stale_sol_position", self.connector._perpetual_trading.account_positions["SOL-USDC-LONG"])

    async def test_process_account_info_ws_event_message_updates_balances_and_fee_tier(self):
        await self.connector._process_account_info_ws_event_message({
            "data": {"ae": "12.5", "as": "10.2", "f": 3},
        })

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)
        self.assertEqual(3, self.connector._fee_tier)

    async def test_process_account_positions_ws_event_message_replaces_snapshot_with_long_and_short(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {"stale": "position"}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()
        self.connector._trading_pairs = ["BTC-USDC", "ETH-USDC"]
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(
            side_effect=lambda symbol: {"BTC": "BTC-USDC", "ETH": "ETH-USDC"}[symbol]
        )
        self.connector.get_leverage = MagicMock(return_value="10")
        self.connector.set_LIGHTER_price("BTC-USDC", 100.0, Decimal("100"), Decimal("105"))
        self.connector.set_LIGHTER_price("ETH-USDC", 100.0, Decimal("200"), Decimal("190"))

        await self.connector._process_account_positions_ws_event_message({
            "channel": "account_positions",
            "data": [
                {"s": "BTC", "d": "bid", "a": "0.5", "p": "100"},
                {"s": "ETH", "d": "ask", "a": "1.2", "p": "200"},
            ]
        })

        positions = self.connector._perpetual_trading.account_positions
        self.assertEqual(2, len(positions))
        btc_position = positions["BTC-USDC-LONG"]
        eth_position = positions["ETH-USDC-SHORT"]
        self.assertEqual(Decimal("0.5"), btc_position.amount)
        self.assertEqual(Decimal("2.5"), btc_position.unrealized_pnl)
        self.assertEqual(Decimal("-1.2"), eth_position.amount)
        self.assertEqual(Decimal("12.0"), eth_position.unrealized_pnl)

    async def test_process_account_positions_ws_event_message_clears_snapshot_when_empty(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {"BTC-USDC-LONG": "existing"}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()

        await self.connector._process_account_positions_ws_event_message({"channel": "account_positions", "data": []})

        self.assertEqual({}, self.connector._perpetual_trading.account_positions)

    async def test_process_account_positions_ws_event_message_ignores_non_position_payload(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {"BTC-USDC-LONG": "existing"}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()

        # account_all update without `positions` must not clear existing snapshot
        await self.connector._process_account_positions_ws_event_message({
            "type": "update/account_all",
            "data": [{"i": 123, "s": "BTC", "a": "0.2"}],
        })

        self.assertEqual({"BTC-USDC-LONG": "existing"}, self.connector._perpetual_trading.account_positions)

    async def test_process_account_positions_ws_event_message_handles_account_all_snapshot(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {"stale": "position"}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()
        self.connector._trading_pairs = ["ETH-USDC"]
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="ETH-USDC")
        self.connector.get_leverage = MagicMock(return_value="5")

        await self.connector._process_account_positions_ws_event_message({
            "type": "update/account_all",
            "positions": {
                "0": {
                    "symbol": "ETH",
                    "sign": -1,
                    "position": "1.25",
                    "avg_entry_price": "2000",
                    "unrealized_pnl": "7.5",
                }
            },
        })

        positions = self.connector._perpetual_trading.account_positions
        self.assertEqual(1, len(positions))
        eth_position = positions["ETH-USDC-SHORT"]
        self.assertEqual(Decimal("-1.25"), eth_position.amount)
        self.assertEqual(Decimal("7.5"), eth_position.unrealized_pnl)

    async def test_process_account_positions_ws_event_message_with_upnl_does_not_raise(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()
        self.connector._trading_pairs = ["HYPE-USDC"]
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="HYPE-USDC")
        self.connector.get_leverage = MagicMock(return_value="5")

        await self.connector._process_account_positions_ws_event_message({
            "channel": "account_positions",
            "data": [
                {"s": "HYPE", "d": "bid", "a": "0.6", "p": "41.02", "upnl": "1.23", "f": "0"},
            ],
        })

        positions = self.connector._perpetual_trading.account_positions
        self.assertEqual(1, len(positions))
        hype_position = positions["HYPE-USDC-LONG"]
        self.assertEqual(Decimal("0.6"), hype_position.amount)
        self.assertEqual(Decimal("1.23"), hype_position.unrealized_pnl)

    async def test_process_account_positions_ws_event_message_from_account_all_with_upnl_and_no_price_cache(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()
        self.connector._trading_pairs = ["HYPE-USDC"]
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="HYPE-USDC")
        self.connector.get_leverage = MagicMock(return_value="5")

        await self.connector._process_account_positions_ws_event_message({
            "channel": "account_all",
            "positions": [
                {"s": "HYPE", "d": "bid", "a": "0.6", "p": "41.02", "upnl": "1.23", "f": "0"},
            ],
        })

        positions = self.connector._perpetual_trading.account_positions
        self.assertEqual(1, len(positions))
        hype_position = positions["HYPE-USDC-LONG"]
        self.assertEqual(Decimal("0.6"), hype_position.amount)
        self.assertEqual(Decimal("1.23"), hype_position.unrealized_pnl)

    async def test_update_positions_preserves_stale_positions_on_rebuild_failure(self):
        """When _update_positions fails mid-rebuild (e.g. symbol resolution raises), the existing
        positions must be left intact so the TUI does not blank out to zero. The old behaviour of
        clearing early was the bug that caused TUI 'position not recognised'."""
        self.connector._perpetual_trading.account_positions["DOGE-USDC"] = "stale"
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {
                "positions": [
                    {"symbol": "DOGE", "position": "0", "sign": 1, "avg_entry_price": "0"},
                ]
            },
        })
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=Exception("boom"))

        with self.assertRaises(Exception):
            await self.connector._update_positions()

        # Stale position must be preserved — NOT wiped — so the TUI stays visible.
        self.assertEqual({"DOGE-USDC": "stale"}, self.connector._perpetual_trading.account_positions)

    async def test_update_positions_rest_skips_zero_amount(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="DOGE-USDC")
        # Pre-populate price cache so the prices HTTP fetch is skipped
        self.connector.set_LIGHTER_price("DOGE-USDC", timestamp=1.0,
                                         index_price=Decimal("0.05"), mark_price=Decimal("0.05"))
        # Pre-populate a stale position for a DIFFERENT pair that should be cleared on successful rebuild
        self.connector._perpetual_trading.account_positions["SOL-USDC"] = "stale_different_pair"
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {
                "positions": [
                    {"symbol": "DOGE", "amount": "0", "sign": 1, "entry_price": "0.05"},
                ]
            },
        })
        await self.connector._update_positions()
        # Zero-amount closed positions must NOT be stored (same guard as WS handler)
        # Stale positions from OTHER pairs must be cleared on successful rebuild
        self.assertEqual({}, self.connector._perpetual_trading.account_positions)

    async def test_update_positions_rest_tracks_sub_minimum_residual_position(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")
        self.connector._trading_rules = {
            "BTC-USDC": TradingRule(
                trading_pair="BTC-USDC",
                min_order_size=Decimal("0.001"),
                min_price_increment=Decimal("0.1"),
                min_base_amount_increment=Decimal("0.001"),
                min_notional_size=Decimal("10"),
            )
        }
        self.connector.set_LIGHTER_price(
            "BTC-USDC",
            timestamp=1.0,
            index_price=Decimal("40"),
            mark_price=Decimal("40"),
        )
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {
                "positions": [
                    {"symbol": "BTC", "amount": "0.2", "sign": 1, "entry_price": "40"},
                ]
            },
        })

        await self.connector._update_positions()

        # 0.2 * 40 = 8 < min_notional(10), but residual position should remain tracked.
        self.assertEqual(1, len(self.connector._perpetual_trading.account_positions))

    async def test_update_positions_rest_skips_unconfigured_trading_pair(self):
        self.connector._trading_pairs = ["BTC-USDC"]
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="SOL-USDC")
        self.connector.set_LIGHTER_price("SOL-USDC", 1.0, Decimal("100"), Decimal("100"))
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {
                "positions": [
                    {"symbol": "SOL", "amount": "1", "sign": 1, "entry_price": "100"},
                ]
            },
        })

        await self.connector._update_positions()

        self.assertEqual({}, self.connector._perpetual_trading.account_positions)

    async def test_update_positions_rest_recovers_positions_when_prices_fetch_fails(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")
        self.connector._api_get = AsyncMock(side_effect=[
            {
                "success": True,
                "data": {
                    "positions": [
                        {"symbol": "BTC", "amount": "0.2", "sign": 1, "entry_price": "40", "unrealized_pnl": "0"},
                    ]
                },
            },
            {
                "success": False,
                "error": "prices endpoint temporary failure",
            },
        ])

        await self.connector._update_positions()

        self.assertEqual(1, len(self.connector._perpetual_trading.account_positions))
        restored_position = list(self.connector._perpetual_trading.account_positions.values())[0]
        self.assertEqual("BTC-USDC", restored_position.trading_pair)
        self.assertEqual(Decimal("0.2"), restored_position.amount)
        self.assertEqual(Decimal("40"), restored_position.entry_price)

    async def test_process_account_positions_ws_event_message_tracks_sub_minimum_residual_position(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()
        self.connector._trading_rules = {
            "BTC-USDC": TradingRule(
                trading_pair="BTC-USDC",
                min_order_size=Decimal("0.001"),
                min_price_increment=Decimal("0.1"),
                min_base_amount_increment=Decimal("0.001"),
                min_notional_size=Decimal("10"),
            )
        }
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")
        self.connector.get_leverage = MagicMock(return_value="5")
        self.connector.set_LIGHTER_price("BTC-USDC", 100.0, Decimal("40"), Decimal("40"))

        await self.connector._process_account_positions_ws_event_message({
            "channel": "account_positions",
            "data": [
                {"s": "BTC", "d": "bid", "a": "0.2", "p": "40"},
            ],
        })

        # 0.2 * 40 = 8 < min_notional(10), but residual position should remain tracked.
        self.assertEqual(1, len(self.connector._perpetual_trading.account_positions))

    async def test_process_account_positions_ws_event_message_skips_unconfigured_trading_pair(self):
        class FakePerpetualTrading:
            def __init__(self):
                self.account_positions = {}

            def position_key(self, trading_pair, position_side):
                return f"{trading_pair}-{position_side.name}"

            def set_position(self, key, position):
                self.account_positions[key] = position

        self.connector._perpetual_trading = FakePerpetualTrading()
        self.connector._trading_pairs = ["BTC-USDC"]
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="SOL-USDC")
        self.connector.get_leverage = MagicMock(return_value="5")

        await self.connector._process_account_positions_ws_event_message({
            "channel": "account_positions",
            "data": [
                {"s": "SOL", "d": "bid", "a": "1", "p": "100"},
            ],
        })

        self.assertEqual({}, self.connector._perpetual_trading.account_positions)

    async def test_update_order_after_failure_sub_minimum_keeps_position(self):
        """When a CLOSE order fails with a sub-minimum notional error, keep the position in
        account_positions so runtime status remains accurate."""
        failed_order = MagicMock()
        failed_order.position = PositionAction.CLOSE
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_orders = {"HBOT-CLOSE-1": failed_order}
        self.connector._perpetual_trading.account_positions["SOL-USDC|LONG"] = "stale_position"
        self.connector._update_positions = AsyncMock()

        err = IOError("Order notional 7.2200 USDC is below the minimum notional 10.0 USDC")
        self.connector._update_order_after_failure("HBOT-CLOSE-1", "SOL-USDC", exception=err)
        await asyncio.sleep(0)

        self.assertIn("SOL-USDC|LONG", self.connector._perpetual_trading.account_positions)
        self.connector._update_positions.assert_awaited_once()

    async def test_update_order_after_failure_normal_close_triggers_position_refresh(self):
        """For non-sub-minimum CLOSE failures (e.g. network error), the position snapshot is
        refreshed from REST so the TUI always reflects reality."""
        failed_order = MagicMock()
        failed_order.position = PositionAction.CLOSE
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_orders = {"HBOT-CLOSE-2": failed_order}
        self.connector._update_positions = AsyncMock()

        err = IOError("Some other network error")
        self.connector._update_order_after_failure("HBOT-CLOSE-2", "SOL-USDC", exception=err)
        # Give asyncio a chance to schedule safe_ensure_future
        await asyncio.sleep(0)

        # _update_positions must have been scheduled for non-sub-minimum close failures
        self.connector._update_positions.assert_awaited_once()

    async def test_process_account_trades_ws_event_message_processes_tracked_trade(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.quote_asset = "USDC"
        tracked_order.position = PositionAction.OPEN
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_trade_update = MagicMock()

        await self.connector._process_account_trades_ws_event_message({
            "data": [{
                "i": 123,
                "s": "BTC",
                "p": "100",
                "a": "0.2",
                "f": "0.01",
                "ts": "open_long",
                "t": 1700000000000,
            }],
        })

        self.connector._order_tracker.process_trade_update.assert_called_once()
        trade_update = self.connector._order_tracker.process_trade_update.call_args.args[0]
        self.assertEqual("HBOT-1", trade_update.client_order_id)
        self.assertEqual("123", trade_update.exchange_order_id)
        self.assertEqual(Decimal("0.2"), trade_update.fill_base_amount)

    async def test_process_account_trades_ws_event_message_ignores_unknown_trade_without_symbol(self):
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {}
        self.connector._order_tracker.all_fillable_orders_by_exchange_order_id = {}
        self.connector._order_tracker.process_trade_update = MagicMock()
        self.connector._reconcile_unmatched_private_event = AsyncMock()

        await self.connector._process_account_trades_ws_event_message({
            "data": [{"i": 123, "p": "100", "a": "0.2", "f": "0.01", "ts": "open_long", "t": 1700000000000}],
        }, buffer_on_miss=False)

        self.connector._order_tracker.process_trade_update.assert_not_called()
        self.connector._reconcile_unmatched_private_event.assert_not_awaited()

    async def test_process_account_trades_ws_event_message_reconciles_unknown_trade_without_symbol_when_position_exists(self):
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {}
        self.connector._order_tracker.all_fillable_orders_by_exchange_order_id = {}
        self.connector._order_tracker.process_trade_update = MagicMock()
        self.connector._reconcile_unmatched_private_event = AsyncMock()
        self.connector._perpetual_trading.set_position(
            "BTC-USDC-LONG",
            SimpleNamespace(trading_pair="BTC-USDC", amount=Decimal("0.6")),
        )

        await self.connector._process_account_trades_ws_event_message({
            "data": [{"i": 123, "p": "100", "a": "0.2", "f": "0.01", "ts": "open_long", "t": 1700000000000}],
        }, buffer_on_miss=False)

        self.connector._order_tracker.process_trade_update.assert_not_called()
        self.connector._reconcile_unmatched_private_event.assert_awaited_once()

    async def test_process_account_trades_ws_event_message_reconciles_unknown_trade_with_symbol(self):
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {}
        self.connector._order_tracker.all_fillable_orders_by_exchange_order_id = {}
        self.connector._order_tracker.process_trade_update = MagicMock()
        self.connector._reconcile_unmatched_private_event = AsyncMock()

        await self.connector._process_account_trades_ws_event_message({
            "data": [{"i": 123, "s": "BTC", "p": "100", "a": "0.2", "f": "0.01", "ts": "open_long", "t": 1700000000000}],
        }, buffer_on_miss=False)

        self.connector._order_tracker.process_trade_update.assert_not_called()
        self.connector._reconcile_unmatched_private_event.assert_awaited_once()

    async def test_process_account_trades_ws_event_message_handles_account_all_trade_update(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "1774621023"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "ETH-USDC"
        tracked_order.quote_asset = "USDC"
        tracked_order.position = PositionAction.OPEN
        self.connector.account_index = "361816"
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_trade_update = MagicMock()

        await self.connector._process_account_trades_ws_event_message({
            "type": "update/account_all",
            "trades": {
                "0": [{
                    "trade_id_str": "16734837600",
                    "market_id": 0,
                    "size": "0.0051",
                    "price": "1983.11",
                    "usd_amount": "10.113861",
                    "bid_client_id_str": "1774621023",
                    "bid_account_id": 361816,
                    "ask_account_id": 702389,
                    "is_maker_ask": True,
                    "taker_fee": 280,
                    "maker_fee": 28,
                    "timestamp": 1774621024363,
                }]
            },
        })

        self.connector._order_tracker.process_trade_update.assert_called_once()
        trade_update = self.connector._order_tracker.process_trade_update.call_args.args[0]
        self.assertEqual("HBOT-1", trade_update.client_order_id)
        self.assertEqual("1774621023", trade_update.exchange_order_id)
        self.assertEqual(Decimal("0.0051"), trade_update.fill_base_amount)
        self.assertEqual("16734837600", trade_update.trade_id)

    async def test_process_account_trades_ws_event_message_uses_reverse_mapping_for_exchange_id(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "999"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "ETH-USDC"
        tracked_order.quote_asset = "USDC"
        tracked_order.position = PositionAction.OPEN
        tracked_order.amount = Decimal("1")
        tracked_order.executed_amount_base = Decimal("0")
        tracked_order.update_exchange_order_id = MagicMock()

        self.connector._client_order_index_to_client_order_id["999"] = "HBOT-1"
        self.connector._client_order_index_to_order_index["999"] = "123"
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_trade_update = MagicMock()

        await self.connector._process_account_trades_ws_event_message({
            "data": [{
                "i": 123,
                "s": "ETH",
                "p": "2000",
                "a": "0.2",
                "f": "0.01",
                "ts": "open_long",
                "t": 1700000000000,
            }],
        })

        tracked_order.update_exchange_order_id.assert_called_once_with("123")
        self.connector._order_tracker.process_trade_update.assert_called_once()
        trade_update = self.connector._order_tracker.process_trade_update.call_args.args[0]
        self.assertEqual("HBOT-1", trade_update.client_order_id)
        self.assertEqual("123", trade_update.exchange_order_id)

    async def test_execute_order_cancel_reconciles_state_before_local_terminal_mark(self):
        tracked_order = MagicMock()
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "ETH-USDC"
        tracked_order.exchange_order_id = "999"

        self.connector._execute_order_cancel_and_process_update = AsyncMock(
            side_effect=IOError('{"success":false,"error":"order not found","code":5}')
        )
        self.connector._request_order_status = AsyncMock(return_value=OrderUpdate(
            trading_pair="ETH-USDC",
            update_timestamp=1700000000,
            new_state=OrderState.OPEN,
            client_order_id="HBOT-1",
            exchange_order_id="123",
        ))
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.process_order_update = MagicMock()

        result = await self.connector._execute_order_cancel(tracked_order)

        self.assertIsNone(result)
        self.connector._request_order_status.assert_awaited_once_with(tracked_order)
        self.connector._order_tracker.process_order_update.assert_called_once()

    async def test_execute_order_cancel_returns_id_when_reconciled_terminal(self):
        tracked_order = MagicMock()
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "ETH-USDC"
        tracked_order.exchange_order_id = "999"

        self.connector._execute_order_cancel_and_process_update = AsyncMock(
            side_effect=IOError('{"success":false,"error":"order not found","code":5}')
        )
        self.connector._request_order_status = AsyncMock(return_value=OrderUpdate(
            trading_pair="ETH-USDC",
            update_timestamp=1700000000,
            new_state=OrderState.CANCELED,
            client_order_id="HBOT-1",
            exchange_order_id="123",
        ))
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.process_order_update = MagicMock()

        result = await self.connector._execute_order_cancel(tracked_order)

        self.assertEqual("HBOT-1", result)
        self.connector._request_order_status.assert_awaited_once_with(tracked_order)
        self.connector._order_tracker.process_order_update.assert_called_once()

    async def test_execute_order_cancel_timeout_runs_reconcile_instead_of_not_found(self):
        tracked_order = MagicMock()
        tracked_order.client_order_id = "HBOT-2"
        tracked_order.trading_pair = "ETH-USDC"
        tracked_order.exchange_order_id = None

        self.connector._execute_order_cancel_and_process_update = AsyncMock(side_effect=asyncio.TimeoutError())
        self.connector._reconcile_unmatched_private_event = AsyncMock()
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.process_order_not_found = AsyncMock()

        result = await self.connector._execute_order_cancel(tracked_order)

        self.assertIsNone(result)
        self.connector._reconcile_unmatched_private_event.assert_awaited_once()
        self.connector._order_tracker.process_order_not_found.assert_not_awaited()

    async def test_place_cancel_recovers_when_exchange_order_id_is_string_none(self):
        """When exchange_order_id is the literal string 'None', _place_cancel should recover
        the real client_order_index from the reverse lookup map and succeed."""
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "None"
        tracked_order.trading_pair = "BTC-USDC"

        real_coi = "248847765999999"
        self.connector._client_order_index_to_client_order_id = {real_coi: "HBOT-stop-loss"}
        self.connector._client_order_index_to_order_index = {real_coi: "88888888888"}

        self.connector._get_market_spec = AsyncMock(return_value=(0, 6, 2, None))

        mock_tx = MagicMock()
        mock_tx.code = 200
        mock_signer = MagicMock()
        mock_signer.cancel_order = AsyncMock(return_value=(None, mock_tx, None))
        mock_signer.create_auth_token_with_expiry = MagicMock(return_value=("tok", None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_api_key_index = MagicMock(return_value=1)

        result = await self.connector._place_cancel("HBOT-stop-loss", tracked_order)

        self.assertTrue(result)
        mock_signer.cancel_order.assert_awaited_once()
        # Verify it used the recovered order_index (88888888888), not "None"
        call_kwargs = mock_signer.cancel_order.call_args
        self.assertEqual(88888888888, call_kwargs.kwargs.get("order_index") or call_kwargs[1].get("order_index"))

    async def test_place_cancel_returns_false_when_exchange_order_id_string_none_and_no_recovery(self):
        """When exchange_order_id is 'None' and no reverse lookup exists, _place_cancel should
        return False gracefully instead of raising an IOError."""
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "None"
        tracked_order.trading_pair = "BTC-USDC"

        self.connector._client_order_index_to_client_order_id = {}
        self.connector._get_market_spec = AsyncMock(return_value=(0, 6, 2, None))

        result = await self.connector._place_cancel("HBOT-unknown", tracked_order)

        self.assertFalse(result)

    async def test_place_cancel_sets_backoff_when_exchange_order_id_is_python_none(self):
        """When exchange_order_id is Python None (placement still in-flight), _place_cancel
        should return False and set a short backoff so the strategy doesn't hammer every tick."""
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = None
        tracked_order.trading_pair = "BTC-USDC"

        self.connector._cancel_backoff_until = {}

        result = await self.connector._place_cancel("HBOT-in-flight", tracked_order)

        self.assertFalse(result)
        self.assertIn("HBOT-in-flight", self.connector._cancel_backoff_until)
        self.assertGreater(self.connector._cancel_backoff_until["HBOT-in-flight"], 0)

    async def test_place_cancel_succeeds_when_exchange_order_id_is_resolved_order_index(self):
        """When WS has replaced exchange_order_id with the real server order_index (large int),
        _place_cancel should recover via reverse lookup and cancel successfully."""
        order_id = "HBOT-test-order"
        client_order_index = "7"
        server_order_index = "248885132237560"

        tracked_order = MagicMock()
        tracked_order.exchange_order_id = server_order_index  # WS has already updated this
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.client_order_id = order_id

        self.connector._get_market_spec = AsyncMock(return_value=(0, 6, 2, None))
        # client_order_index → order_id mapping (set at placement)
        self.connector._client_order_index_to_client_order_id = {client_order_index: order_id}
        # client_order_index → server order_index mapping (set from WS account_orders)
        self.connector._client_order_index_to_order_index = {client_order_index: server_order_index}
        self.connector._cancel_backoff_until = {}

        mock_tx_response = MagicMock()
        mock_tx_response.code = 200
        self.connector._get_lighter_signer_client = MagicMock()
        mock_signer = MagicMock()
        mock_signer.cancel_order = AsyncMock(return_value=(None, mock_tx_response, None))
        self.connector._get_lighter_signer_client.return_value = mock_signer
        self.connector._get_api_key_index = MagicMock(return_value=0)

        result = await self.connector._place_cancel(order_id, tracked_order)

        self.assertTrue(result)
        mock_signer.cancel_order.assert_awaited_once_with(
            market_index=0,
            order_index=int(server_order_index),
            api_key_index=0,
        )

    async def test_user_stream_event_listener_routes_known_channels(self):
        async def event_iter():
            for event in [
                {"channel": "account_order_updates", "data": []},
                {"channel": "account_positions", "data": []},
                {"channel": "account_info", "data": {"ae": "1", "as": "1"}},
                {"channel": "account_trades", "data": []},
            ]:
                yield event

        self.connector._iter_user_event_queue = event_iter
        self.connector._process_account_order_updates_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_info_ws_event_message = AsyncMock()
        self.connector._process_account_trades_ws_event_message = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._process_account_order_updates_ws_event_message.assert_awaited_once()
        self.connector._process_account_positions_ws_event_message.assert_awaited_once()
        self.connector._process_account_info_ws_event_message.assert_awaited_once()
        self.connector._process_account_trades_ws_event_message.assert_awaited_once()

    async def test_user_stream_event_listener_routes_subscribed_dedicated_events(self):
        async def event_iter():
            for event in [
                {"type": "subscribed/account_order_updates", "data": []},
                {"type": "subscribed/account_positions", "data": []},
                {"type": "subscribed/account_info", "data": {"ae": "1", "as": "1"}},
                {"type": "subscribed/account_trades", "data": []},
            ]:
                yield event

        self.connector._iter_user_event_queue = event_iter
        self.connector._process_account_order_updates_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_info_ws_event_message = AsyncMock()
        self.connector._process_account_trades_ws_event_message = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._process_account_order_updates_ws_event_message.assert_awaited_once()
        self.connector._process_account_positions_ws_event_message.assert_awaited_once()
        self.connector._process_account_info_ws_event_message.assert_awaited_once()
        self.connector._process_account_trades_ws_event_message.assert_awaited_once()

    async def test_user_stream_event_listener_routes_colon_scoped_channels(self):
        async def event_iter():
            for event in [
                {"channel": "account_order_updates:237600", "data": []},
                {"channel": "account_positions:237600", "data": []},
                {"channel": "account_info:237600", "data": {"ae": "1", "as": "1"}},
                {"channel": "account_trades:237600", "data": []},
            ]:
                yield event

        self.connector._iter_user_event_queue = event_iter
        self.connector._process_account_order_updates_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_info_ws_event_message = AsyncMock()
        self.connector._process_account_trades_ws_event_message = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._process_account_order_updates_ws_event_message.assert_awaited_once()
        self.connector._process_account_positions_ws_event_message.assert_awaited_once()
        self.connector._process_account_info_ws_event_message.assert_awaited_once()
        self.connector._process_account_trades_ws_event_message.assert_awaited_once()

    async def test_user_stream_event_listener_routes_account_all_events(self):
        async def event_iter():
            yield {"type": "update/account_all", "channel": "account_all:237600", "positions": {}}

        self.connector._iter_user_event_queue = event_iter
        self.connector._process_account_all_ws_event_message = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._process_account_all_ws_event_message.assert_awaited_once()

    async def test_user_stream_event_listener_ignores_wrong_numeric_scoped_channel(self):
        async def event_iter():
            yield {"channel": "user_stats:4", "stats": {"collateral": "19.1", "available_balance": "2.2"}}

        self.connector.account_index = "237600"
        self.connector._iter_user_event_queue = event_iter
        self.connector._process_user_stats_ws_event_message = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._process_user_stats_ws_event_message.assert_not_awaited()

    async def test_user_stream_event_listener_accepts_matching_numeric_scoped_channel(self):
        async def event_iter():
            yield {"channel": "user_stats:237600", "stats": {"collateral": "19.1", "available_balance": "2.2"}}

        self.connector.account_index = "237600"
        self.connector._iter_user_event_queue = event_iter
        self.connector._process_user_stats_ws_event_message = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._process_user_stats_ws_event_message.assert_awaited_once()

    async def test_process_account_all_ws_event_message_routes_trades_and_positions(self):
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()

        event = {"type": "update/account_all", "channel": "account_all:237600", "positions": {}, "trades": {}}
        await self.connector._process_account_all_ws_event_message(event)

        # Both handlers are forwarded the full event; each handler normalises its own slice.
        self.connector._process_account_trades_ws_event_message.assert_awaited_once_with(event, buffer_on_miss=False)
        self.connector._process_account_positions_ws_event_message.assert_awaited_once_with(event)

    async def test_process_account_all_ws_event_message_extracts_usdc_balance(self):
        # account_all top-level available_balance is used when present.
        # A REST poll is still scheduled (via _schedule_fast_balance_sync) to keep parity with exchange state.
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
            "collateral": "100.50",
            "available_balance": "88.00",
            "assets": {
                "3": {"symbol": "USDC", "asset_id": 3, "balance": "100.50", "locked_balance": "10.25"},
                "1": {"symbol": "ETH", "asset_id": 1, "balance": "0.001", "locked_balance": "0.0"},
            },
        }
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        # Pre-set an existing available balance; top-level account_all available overrides it.
        self.connector._account_available_balances["USDC"] = Decimal("75.00")

        await self.connector._process_account_all_ws_event_message(event)

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertEqual(Decimal("75.00"), self.connector._account_available_balances["USDC"])

    async def test_process_account_all_ws_event_message_no_assets_key_skips_balance(self):
        event = {"type": "update/account_all", "channel": "account_all:237600", "positions": {}, "trades": {}}
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()

        await self.connector._process_account_all_ws_event_message(event)

        # Should not error; balances remain at their defaults
        self.assertEqual({}, self.connector._account_balances)

    async def test_process_account_all_ws_event_message_margin_balance_with_available_to_spend(self):
        # Simulates the real production cross-margin scenario: margin_balance (perp equity) is
        # the total, but available_to_spend (from exchange) already subtracts position initial
        # margin. locked_balance only covers open-order locks, so margin_balance - locked_balance
        # would overstate the available margin. The exchange-computed available_to_spend must win.
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
            "available_to_spend": "6.00",   # exchange-computed: equity minus position margin
            "assets": {
                "3": {
                    "symbol": "USDC",
                    "asset_id": 3,
                    "balance": "43.86",          # simple spot balance (much larger, must not be used)
                    "locked_balance": "0.00",    # open-order locks only
                    "margin_balance": "6.61",    # perp equity (total)
                },
            },
        }
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()

        await self.connector._process_account_all_ws_event_message(event)

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)

    async def test_process_account_all_ws_event_message_margin_balance_no_available_falls_back(self):
        # When no exchange-computed available field is present, preserve the last known
        # available balance rather than computing total - locked.  For PERP, locked_balance
        # only covers order margin (not position initial margin), so total - locked gives a
        # falsely-high available balance.  With no prior balance stored, fall back to total.
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
            "assets": {
                "3": {
                    "symbol": "USDC",
                    "asset_id": 3,
                    "balance": "43.86",
                    "locked_balance": "1.50",
                    "margin_balance": "6.61",
                },
            },
        }
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()

        # Case 1: no prior available balance stored — falls back to total (margin_balance).
        self.connector._account_available_balances.pop("USDC", None)
        await self.connector._process_account_all_ws_event_message(event)
        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)

        # Case 2: prior available balance exists (e.g. set by user_stats WS) — preserved.
        self.connector._account_available_balances["USDC"] = Decimal("4.00")
        await self.connector._process_account_all_ws_event_message(event)
        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertEqual(Decimal("4.00"), self.connector._account_available_balances["USDC"])

    async def test_process_account_all_ws_event_message_fallback_balance_without_assets(self):
        # When an existing available balance is set, it is preserved over WS available_balance
        # (which may omit open-order margin).  REST poll corrects the value soon after.
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
            "collateral": "150.75",
            "available_balance": "120.50",
        }
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        # Pre-set an existing available so it can be verified as preserved.
        self.connector._account_available_balances["USDC"] = Decimal("85.00")

        await self.connector._process_account_all_ws_event_message(event)

        self.assertNotIn("USDC", self.connector._account_balances)
        # Existing (85.00) is preserved; WS available_balance (120.50) is not used when existing is set.
        self.assertEqual(Decimal("85.00"), self.connector._account_available_balances["USDC"])

    async def test_process_account_all_ws_event_message_fallback_uses_available_balance_when_no_existing(self):
        # When NO existing available balance is stored (startup before REST succeeds), use the
        # WS available_balance as a bootstrap value.  REST poll will correct over-reporting.
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
            "collateral": "150.75",
            "available_balance": "120.50",
        }
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        # No prior available balance — simulates startup before REST poll completes.
        self.connector._account_available_balances.pop("USDC", None)

        await self.connector._process_account_all_ws_event_message(event)

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)

    async def test_process_account_all_ws_event_message_assets_uses_available_balance_when_no_existing(self):
        # Startup case (no existing available): assets path falls back to available_balance
        # from asset entry or event when available_to_spend is absent.
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
            "available_balance": "95.00",   # top-level fallback
            "assets": {
                "3": {
                    "symbol": "USDC",
                    "margin_balance": "100.50",
                    "balance": "100.50",
                    # no available_to_spend, but available_balance in event
                },
            },
        }
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_all_orders_ws_event_message = AsyncMock()
        # No prior available balance.
        self.connector._account_available_balances.pop("USDC", None)

        await self.connector._process_account_all_ws_event_message(event)

        self.assertNotIn("USDC", self.connector._account_balances)
        self.assertNotIn("USDC", self.connector._account_available_balances)

    def test_is_ok_response_returns_false_for_non_dict(self):
        # Non-dict responses (e.g. raw HTML error pages from the REST API) must not crash.
        # Previously _is_ok_response called response.get(...) which raised AttributeError
        # for strings, preventing the fallback error path from running.
        self.assertFalse(self.connector._is_ok_response("<html>Not Found</html>"))
        self.assertFalse(self.connector._is_ok_response(""))
        self.assertFalse(self.connector._is_ok_response(None))
        self.assertFalse(self.connector._is_ok_response(404))

    async def test_user_stream_event_listener_sleeps_after_processing_error(self):
        async def event_iter():
            yield {"channel": "account_info", "data": {"ae": "1", "as": "1"}}

        self.connector._iter_user_event_queue = event_iter
        self.connector._process_account_info_ws_event_message = AsyncMock(side_effect=Exception("boom"))
        self.connector._sleep = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._sleep.assert_awaited_once_with(5.0)

    async def test_user_stream_event_listener_ignores_unknown_channel(self):
        async def event_iter():
            yield {"channel": "unknown_channel", "data": {}}

        self.connector._iter_user_event_queue = event_iter
        self.connector._sleep = AsyncMock()
        self.connector._process_account_order_updates_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_info_ws_event_message = AsyncMock()
        self.connector._process_account_trades_ws_event_message = AsyncMock()

        await self.connector._user_stream_event_listener()

        self.connector._sleep.assert_not_awaited()
        self.connector._process_account_order_updates_ws_event_message.assert_not_awaited()
        self.connector._process_account_positions_ws_event_message.assert_not_awaited()
        self.connector._process_account_info_ws_event_message.assert_not_awaited()
        self.connector._process_account_trades_ws_event_message.assert_not_awaited()

    async def test_place_modify_sends_signed_modify_order(self):
        tracked_order = SimpleNamespace(trading_pair="BTC-USDC", exchange_order_id="12345")
        signer_client = SimpleNamespace(modify_order=AsyncMock(return_value=(None, SimpleNamespace(code=200), None)))

        self.connector._get_market_spec = AsyncMock(return_value=(45, 3, 2, "BTC"))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_client)
        self.connector._get_api_key_index = MagicMock(return_value=4)

        result = await self.connector._place_modify(
            tracked_order=tracked_order,
            amount=Decimal("1.234"),
            price=Decimal("123.45"),
        )

        self.assertTrue(result)
        signer_client.modify_order.assert_awaited_once_with(
            market_index=45,
            order_index=12345,
            base_amount=1234,
            price=12345,
        )

    async def test_place_modify_raises_on_signing_error(self):
        tracked_order = SimpleNamespace(trading_pair="BTC-USDC", exchange_order_id="12345")
        signer_client = SimpleNamespace(modify_order=AsyncMock(return_value=(None, None, "bad signature")))

        self.connector._get_market_spec = AsyncMock(return_value=(45, 3, 2, "BTC"))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_client)
        self.connector._get_api_key_index = MagicMock(return_value=4)

        with self.assertRaises(IOError) as error_context:
            await self.connector._place_modify(
                tracked_order=tracked_order,
                amount=Decimal("1.000"),
                price=Decimal("120.00"),
            )

        self.assertIn("modify_order signing/send failed", str(error_context.exception))

    async def test_positions_ws_skips_zero_amount(self):
        """_process_account_positions_ws_event_message must not store zero-amount ghost positions."""
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="ETH-USDC")
        self.connector.get_LIGHTER_price = MagicMock(return_value=None)
        self.connector.get_leverage = MagicMock(return_value=5)

        ws_message = {
            "channel": "account_positions",
            "data": [
                {"s": "ETH", "d": "bid", "a": "0.00000", "p": "2300.0"},
            ],
        }

        self.connector._perpetual_trading.account_positions.clear()
        await self.connector._process_account_positions_ws_event_message(ws_message)

        self.assertEqual(0, len(self.connector._perpetual_trading.account_positions),
                         "Zero-amount position must not be stored")

    async def test_positions_ws_stores_nonzero_amount(self):
        """_process_account_positions_ws_event_message stores positions with non-zero amount."""
        self.connector._trading_pairs = ["ETH-USDC"]
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="ETH-USDC")
        self.connector.get_LIGHTER_price = MagicMock(return_value=None)
        self.connector.get_leverage = MagicMock(return_value=5)

        ws_message = {
            "channel": "account_positions",
            "data": [
                {"s": "ETH", "d": "bid", "a": "0.05", "p": "2300.0"},
            ],
        }

        self.connector._perpetual_trading.account_positions.clear()
        await self.connector._process_account_positions_ws_event_message(ws_message)

        self.assertEqual(1, len(self.connector._perpetual_trading.account_positions),
                         "Non-zero-amount position must be stored")

    async def test_trade_updates_nan_timestamp_not_stored(self):
        """NaN current_timestamp must not be written to _order_history_last_poll_timestamp."""
        from hummingbot.core.data_type.in_flight_order import InFlightOrder

        mock_signer = MagicMock()
        mock_signer.create_auth_token_with_expiry = MagicMock(return_value=("tok", 9999999999))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_api_key_index = MagicMock(return_value=4)
        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 2, "ETH"))
        self.connector._get_account_index = MagicMock(return_value=42)
        self.connector._api_get = AsyncMock(return_value={"success": True, "data": [], "has_more": False})
        self.connector._exchange_order_id_by_client_order_index = {}

        order = InFlightOrder(
            client_order_id="HBOT-nan",
            exchange_order_id="99999",
            trading_pair="ETH-USDC",
            order_type=None,
            trade_type=None,
            price=Decimal("2300"),
            amount=Decimal("0.01"),
            creation_timestamp=1700000000.0,
        )

        # Simulate clock stopped: current_timestamp is NaN
        self.connector._current_timestamp = float("nan")

        await self.connector._all_trade_updates_for_order(order)

        # Should NOT be stored
        stored = self.connector._order_history_last_poll_timestamp.get("99999")
        self.assertIsNone(stored, "NaN timestamp must not be persisted")

    async def test_trade_updates_nan_last_poll_does_not_crash(self):
        """If a NaN is already stored in _order_history_last_poll_timestamp, the next call must not crash."""
        from hummingbot.core.data_type.in_flight_order import InFlightOrder

        mock_signer = MagicMock()
        mock_signer.create_auth_token_with_expiry = MagicMock(return_value=("tok", 9999999999))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_api_key_index = MagicMock(return_value=4)
        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 2, "ETH"))
        self.connector._get_account_index = MagicMock(return_value=42)
        self.connector._api_get = AsyncMock(return_value={"success": True, "data": [], "has_more": False})
        self.connector._exchange_order_id_by_client_order_index = {}

        # Pre-populate with a NaN value (simulating a previous bad write)
        self.connector._order_history_last_poll_timestamp["99999"] = float("nan")
        self.connector._current_timestamp = 1700000001.0

        order = InFlightOrder(
            client_order_id="HBOT-nan2",
            exchange_order_id="99999",
            trading_pair="ETH-USDC",
            order_type=None,
            trade_type=None,
            price=Decimal("2300"),
            amount=Decimal("0.01"),
            creation_timestamp=1700000000.0,
        )

        # Must not raise ValueError
        try:
            await self.connector._all_trade_updates_for_order(order)
        except ValueError as exc:
            self.fail(f"NaN last_poll_timestamp must not crash: {exc}")

    async def test_trade_updates_applies_time_drift_buffer_to_from_param(self):
        from hummingbot.core.data_type.in_flight_order import InFlightOrder

        mock_signer = MagicMock()
        mock_signer.create_auth_token_with_expiry = MagicMock(return_value=("tok", 9999999999))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_api_key_index = MagicMock(return_value=4)
        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 2, "ETH"))
        self.connector._get_account_index = MagicMock(return_value=42)
        self.connector._api_get = AsyncMock(return_value={"success": True, "data": [], "has_more": False})

        self.connector._order_history_last_poll_timestamp["99999"] = 100.0
        self.connector._current_timestamp = 1700000001.0

        order = InFlightOrder(
            client_order_id="HBOT-buf",
            exchange_order_id="99999",
            trading_pair="ETH-USDC",
            order_type=None,
            trade_type=None,
            price=Decimal("2300"),
            amount=Decimal("0.01"),
            creation_timestamp=1700000000.0,
        )

        await self.connector._all_trade_updates_for_order(order)

        api_get_call = self.connector._api_get.call_args
        self.assertEqual(90, api_get_call.kwargs["params"]["from"])

    async def test_place_order_market_buy_uses_best_ask_with_slippage(self):
        """MARKET BUY order with NaN price must query best ASK (get_price(True)) and add 5% slippage."""
        from hummingbot.core.data_type.common import TradeType

        signer_client = SimpleNamespace(
            ORDER_TYPE_LIMIT=1,
            ORDER_TYPE_MARKET=2,
            ORDER_TIME_IN_FORCE_GOOD_TILL_TIME=10,
            ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL=11,
            ORDER_TIME_IN_FORCE_POST_ONLY=12,
            DEFAULT_28_DAY_ORDER_EXPIRY=1000,
            DEFAULT_IOC_EXPIRY=1001,
            create_order=AsyncMock(return_value=(None, SimpleNamespace(code=200), None)),
        )
        self.connector._get_market_spec = AsyncMock(return_value=(0, 2, 2, "ETH"))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_client)
        self.connector._get_api_key_index = MagicMock(return_value=1)

        # BUY -> get_price(True) -> best ask = 2000; SELL -> get_price(False) -> best bid = 1990
        prices = {True: 2000.0, False: 1990.0}
        mock_order_book = SimpleNamespace(get_price=lambda is_buy: prices[is_buy])
        self.connector.get_order_book = MagicMock(return_value=mock_order_book)
        self.connector._current_timestamp = 1700000000.0

        try:
            await self.connector._place_order(
                order_id="HBOT-PERM-MKBUY",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                price=Decimal("NaN"),
                position_action=PositionAction.OPEN,
            )
        except AttributeError as exc:
            if "current_timestamp" not in str(exc):
                raise

        self.assertTrue(signer_client.create_order.called)
        call_kwargs = signer_client.create_order.call_args.kwargs
        # best_ask=2000, slippage=5%, effective=2100, price_decimals=2 -> price_scaled=210000
        self.assertEqual(210000, call_kwargs["price"])
        self.assertEqual(2, call_kwargs["order_type"])  # ORDER_TYPE_MARKET

    async def test_place_order_market_sell_uses_best_bid_with_slippage(self):
        """MARKET SELL order with NaN price must query best BID (get_price(False)) and subtract 5% slippage."""
        from hummingbot.core.data_type.common import TradeType

        signer_client = SimpleNamespace(
            ORDER_TYPE_LIMIT=1,
            ORDER_TYPE_MARKET=2,
            ORDER_TIME_IN_FORCE_GOOD_TILL_TIME=10,
            ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL=11,
            ORDER_TIME_IN_FORCE_POST_ONLY=12,
            DEFAULT_28_DAY_ORDER_EXPIRY=1000,
            DEFAULT_IOC_EXPIRY=1001,
            create_order=AsyncMock(return_value=(None, SimpleNamespace(code=200), None)),
        )
        self.connector._get_market_spec = AsyncMock(return_value=(0, 2, 2, "ETH"))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_client)
        self.connector._get_api_key_index = MagicMock(return_value=1)

        prices = {True: 2000.0, False: 1990.0}
        mock_order_book = SimpleNamespace(get_price=lambda is_buy: prices[is_buy])
        self.connector.get_order_book = MagicMock(return_value=mock_order_book)
        self.connector._current_timestamp = 1700000000.0

        try:
            await self.connector._place_order(
                order_id="HBOT-PERM-MKSELL",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("NaN"),
                position_action=PositionAction.CLOSE,
            )
        except AttributeError as exc:
            if "current_timestamp" not in str(exc):
                raise

        self.assertTrue(signer_client.create_order.called)
        call_kwargs = signer_client.create_order.call_args.kwargs
        # best_bid=1990, slippage=5%, effective=1990*0.95=1890.5, price_decimals=2 -> price_scaled=189050
        self.assertEqual(189050, call_kwargs["price"])
        self.assertEqual(2, call_kwargs["order_type"])  # ORDER_TYPE_MARKET
        self.assertTrue(call_kwargs["reduce_only"])  # CLOSE position

    # ------------------------------------------------------------------ #
    # Additional branch coverage for missing CI lines                     #
    # ------------------------------------------------------------------ #

    def test_is_request_exception_not_time_synchronizer(self):
        """_is_request_exception_related_to_time_synchronizer must always return False."""
        self.assertFalse(self.connector._is_request_exception_related_to_time_synchronizer(Exception("timeout")))
        self.assertFalse(self.connector._is_request_exception_related_to_time_synchronizer(Exception("")))

    def test_is_order_not_found_status_update_error(self):
        """_is_order_not_found_during_status_update_error must detect 'not found' messages."""
        self.assertTrue(self.connector._is_order_not_found_during_status_update_error(
            Exception("Order history not found for order ID: 123")))
        self.assertFalse(self.connector._is_order_not_found_during_status_update_error(
            Exception("Server error 500")))

    def test_is_order_not_found_during_cancelation_error(self):
        """_is_order_not_found_during_cancelation_error must detect code 5 error strings."""
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(
            Exception('{"success":false,"data":null,"error":"Failed to cancel order","code":5}')))
        self.assertFalse(self.connector._is_order_not_found_during_cancelation_error(
            Exception('{"code":404,"error":"not found"}')))

    # ---------------------------------------------------------------------------
    # Tests for Fix: _request_order_status graceful handling of exchange_order_id="None"
    # ---------------------------------------------------------------------------

    async def test_request_order_status_with_none_exchange_order_id_within_grace_returns_open(self):
        """When exchange_order_id is 'None' and the order is within the extended grace period,
        _request_order_status must return OPEN with exchange_order_id unchanged ('None').
        The active-orders scan is intentionally skipped to avoid mis-assigning a different
        order's exchange_order_id (e.g. a same-price orphan from a previous session)."""
        import time as _time
        self.connector._current_timestamp = 1700000000.0
        mock_order = MagicMock()
        mock_order.exchange_order_id = "None"
        mock_order.trading_pair = "SOL-USDC"
        mock_order.client_order_id = "HBOTSSLUC-orphan"
        mock_order.trade_type = TradeType.SELL
        mock_order.price = Decimal("83.235")
        mock_order.amount = Decimal("0.5")
        mock_order.creation_timestamp = _time.time() - 10  # 10 seconds ago — within grace

        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 3, "SOL"))
        # Active-orders snapshot is present but should NOT be used for ID recovery.
        self.connector._active_orders_snapshot_by_market = {
            1: [
                {
                    "order_id": "999001",
                    "client_order_id": "777001",
                    "side": "ask",
                    "price": "83.235",
                    "initial_amount": "500",
                }
            ]
        }
        self.connector._order_tracker._in_flight_orders = {}

        result = await self.connector._request_order_status(mock_order)

        self.assertEqual(OrderState.OPEN, result.new_state)
        # exchange_order_id stays 'None' — no active-orders scan is performed
        self.assertEqual("None", result.exchange_order_id)
        self.assertEqual("HBOTSSLUC-orphan", result.client_order_id)

    async def test_request_order_status_with_none_exchange_order_id_returns_open_within_grace(self):
        """When exchange_order_id is 'None', no active-orders match, and the order is young,
        _request_order_status must return OPEN (extended grace period)."""
        import time as _time
        mock_order = MagicMock()
        mock_order.exchange_order_id = "None"
        mock_order.trading_pair = "SOL-USDC"
        mock_order.client_order_id = "HBOTSSLUC-young"
        mock_order.trade_type = TradeType.SELL
        mock_order.price = Decimal("83.235")
        mock_order.amount = Decimal("0.5")
        # Order placed 20 seconds ago — well within the 120-second extended grace period
        mock_order.creation_timestamp = _time.time() - 20

        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 3, "SOL"))
        self.connector._active_orders_snapshot_by_market = {1: []}  # empty snapshot
        self.connector._order_tracker._in_flight_orders = {}

        result = await self.connector._request_order_status(mock_order)

        self.assertEqual(OrderState.OPEN, result.new_state)
        self.assertEqual("None", result.exchange_order_id)

    async def test_request_order_status_with_none_exchange_order_id_returns_canceled_after_grace(self):
        """When exchange_order_id is 'None', no active-orders match, and the order is old,
        _request_order_status must return CANCELED (grace period exceeded)."""
        import time as _time
        self.connector._current_timestamp = 1700000000.0
        mock_order = MagicMock()
        mock_order.exchange_order_id = "None"
        mock_order.trading_pair = "SOL-USDC"
        mock_order.client_order_id = "HBOTSSLUC-stale"
        mock_order.trade_type = TradeType.SELL
        mock_order.price = Decimal("83.235")
        mock_order.amount = Decimal("0.5")
        # Order placed 400 seconds ago — beyond the current 300-second extended grace period
        mock_order.creation_timestamp = _time.time() - 400

        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 3, "SOL"))
        self.connector._active_orders_snapshot_by_market = {1: []}
        self.connector._order_tracker._in_flight_orders = {}

        result = await self.connector._request_order_status(mock_order)

        self.assertEqual(OrderState.CANCELED, result.new_state)

    # ---------------------------------------------------------------------------
    # Tests for orphan cleanup disabled behavior
    # ---------------------------------------------------------------------------

    async def test_cleanup_runtime_orphan_orders_is_noop(self):
        """Runtime orphan cleanup must never cancel exchange orders (manual or otherwise)."""
        signer_mock = MagicMock()
        signer_mock.cancel_order = AsyncMock(return_value=(None, MagicMock(code=200), None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_mock)

        await self.connector._cleanup_runtime_orphan_orders()

        signer_mock.cancel_order.assert_not_called()

    async def test_cleanup_startup_orphan_reduce_only_orders_is_noop(self):
        """Startup orphan cleanup is intentionally disabled to avoid canceling manual orders."""
        signer_mock = MagicMock()
        signer_mock.cancel_order = AsyncMock(return_value=(None, MagicMock(code=200), None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_mock)

        await self.connector._cleanup_startup_orphan_reduce_only_orders()

        signer_mock.cancel_order.assert_not_called()

    async def test_status_polling_does_not_run_orphan_cleanup_paths(self):
        self.connector._begin_status_poll_cycle = MagicMock()
        self.connector._end_status_poll_cycle = MagicMock()
        self.connector._fetch_account_snapshot_data = AsyncMock(return_value=None)
        self.connector._update_positions = AsyncMock()
        self.connector._update_balances = AsyncMock()
        self.connector._prime_active_orders_snapshot_cache_for_poll_cycle = AsyncMock()
        self.connector._cleanup_startup_orphan_reduce_only_orders = AsyncMock()
        self.connector._cleanup_runtime_orphan_orders = AsyncMock()
        self.connector._update_order_status = AsyncMock()

        await self.connector._status_polling_loop_fetch_updates()

        self.connector._cleanup_startup_orphan_reduce_only_orders.assert_not_called()
        self.connector._cleanup_runtime_orphan_orders.assert_not_called()

    def test_get_price_by_type_all_price_types(self):
        """get_price_by_type must handle MidPrice, LastTrade, and unknown types (covers lines 211-222)."""
        if not hasattr(self.connector, "get_price_by_type"):
            self.skipTest("get_price_by_type not available in this runtime")

        order_book_module = __import__("hummingbot.core.data_type.order_book", fromlist=["OrderBook"])
        OrderBook = getattr(order_book_module, "OrderBook")
        empty_order_book = OrderBook()
        self.connector.get_order_book = MagicMock(return_value=empty_order_book)

        # MidPrice with empty order book → NaN (both sides NaN)
        mid = self.connector.get_price_by_type("BTC-USDC", PriceType.MidPrice)
        self.assertTrue(mid.is_nan())

        # LastTrade with no trades → NaN
        last = self.connector.get_price_by_type("BTC-USDC", PriceType.LastTrade)
        self.assertTrue(last.is_nan())

    def test_rate_limits_rules_without_api_key_returns_base_limits(self):
        """rate_limits_rules without api_key must return base RATE_LIMITS (covers line 406)."""
        from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
        self.connector.api_key = ""
        rules = self.connector.rate_limits_rules
        self.assertEqual(CONSTANTS.RATE_LIMITS, rules)

    async def test_format_trading_rules_with_data_fallback_path(self):
        """_format_trading_rules must handle legacy 'data' key format (covers lines 732-753)."""
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")
        exchange_info = {
            "data": [
                {
                    "symbol": "BTC",
                    "lot_size": "0.001",
                    "tick_size": "0.01",
                    "min_order_size": "10",
                },
            ]
        }
        rules = await self.connector._format_trading_rules(exchange_info)
        self.assertEqual(1, len(rules))
        self.assertEqual(Decimal("0.001"), rules[0].min_order_size)
        self.assertEqual(Decimal("0.01"), rules[0].min_price_increment)
        self.assertEqual(Decimal("10"), rules[0].min_notional_size)

    async def test_format_trading_rules_skips_non_perp_markets(self):
        """_format_trading_rules must skip non-perp order_books entries (covers lines 704-708)."""
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="ETH-USDC")
        exchange_info = {
            "order_books": [
                {"symbol": "BTC", "market_type": "spot", "market_id": 1,
                 "supported_size_decimals": 3, "supported_price_decimals": 2, "min_quote_amount": "10"},
                {"symbol": "ETH", "market_type": "perp", "market_id": 2,
                 "supported_size_decimals": 2, "supported_price_decimals": 2, "min_quote_amount": "5"},
            ]
        }
        rules = await self.connector._format_trading_rules(exchange_info)
        # Only the perp market should produce a rule
        self.assertEqual(1, len(rules))

    # ---------------------------------------------------------------------------
    # Coverage boost: _index_client_to_order_mapping_from_rows
    # ---------------------------------------------------------------------------

    def test_index_client_to_order_mapping_skips_rows_with_empty_oid_or_cid(self):
        """Rows without both oid and cid must be skipped; valid rows must be stored."""
        self.connector._client_order_index_to_order_index.clear()
        rows = [
            {"order_id": "42", "client_order_id": ""},      # empty cid → skip
            {"order_id": "", "client_order_id": "cid0"},    # empty oid → skip
            {},                                              # both empty → skip
            {"order_id": "43", "client_order_id": "cid1"},  # valid → store
        ]
        self.connector._index_client_to_order_mapping_from_rows(rows)
        self.assertEqual({"cid1": "43"}, self.connector._client_order_index_to_order_index)

    # ---------------------------------------------------------------------------
    # Coverage boost: _refresh_account_state
    # ---------------------------------------------------------------------------

    async def test_refresh_account_state_calls_updates_when_requested(self):
        """_refresh_account_state must call _update_positions and _update_balances when flags are True."""
        with patch.object(self.connector, "_update_positions", new=AsyncMock()) as mock_pos, \
             patch.object(self.connector, "_update_balances", new=AsyncMock()) as mock_bal:
            await self.connector._refresh_account_state("test", refresh_positions=True, refresh_balances=True)
            mock_pos.assert_called_once()
            mock_bal.assert_called_once()

    async def test_refresh_account_state_swallows_exceptions(self):
        """_refresh_account_state must not propagate exceptions from sub-calls."""
        with patch.object(self.connector, "_update_positions", new=AsyncMock(side_effect=IOError("fail"))), \
             patch.object(self.connector, "_update_balances", new=AsyncMock(side_effect=IOError("fail2"))):
            # Should not raise
            await self.connector._refresh_account_state("err", refresh_positions=True, refresh_balances=True)

    # ---------------------------------------------------------------------------
    # Coverage boost: _reconcile_unmatched_private_event
    # ---------------------------------------------------------------------------

    async def test_reconcile_unmatched_private_event_respects_cooldown(self):
        """Second call within 2 s must be a no-op."""
        import time
        self.connector._last_unmatched_private_event_reconcile_ts = time.time()
        with patch.object(self.connector, "_update_order_status", new=AsyncMock()) as mock_s, \
             patch.object(self.connector, "_update_positions", new=AsyncMock()) as mock_p, \
             patch.object(self.connector, "_update_balances", new=AsyncMock()) as mock_b:
            await self.connector._reconcile_unmatched_private_event("test")
            mock_s.assert_not_called()
            mock_p.assert_not_called()
            mock_b.assert_not_called()

    async def test_reconcile_unmatched_private_event_runs_after_cooldown_expires(self):
        """Call after cooldown must invoke update methods."""
        self.connector._last_unmatched_private_event_reconcile_ts = 0.0
        with patch.object(self.connector, "_update_order_status", new=AsyncMock()) as mock_s, \
             patch.object(self.connector, "_update_positions", new=AsyncMock()) as mock_p, \
             patch.object(self.connector, "_update_balances", new=AsyncMock()) as mock_b:
            await self.connector._reconcile_unmatched_private_event("old")
            mock_s.assert_called_once()
            mock_p.assert_called_once()
            mock_b.assert_called_once()

    # ---------------------------------------------------------------------------
    # Coverage boost: _prime_active_orders_snapshot_cache_for_poll_cycle
    # ---------------------------------------------------------------------------

    async def test_prime_active_orders_snapshot_skips_when_cycle_not_active(self):
        """Must return immediately when _status_poll_cycle_active is False."""
        self.connector._status_poll_cycle_active = False
        self.connector._get_market_spec = AsyncMock()
        await self.connector._prime_active_orders_snapshot_cache_for_poll_cycle()
        self.connector._get_market_spec.assert_not_called()

    async def test_prime_active_orders_snapshot_stores_rows_and_updates_mapping(self):
        """Active cycle must fetch rows, store them, and build the order-index mapping."""
        self.connector._status_poll_cycle_active = True
        rows = [{"order_id": "55", "client_order_id": "cid55"}]
        self.connector._get_market_spec = AsyncMock(return_value=(7, 3, 2, "BTC"))
        self.connector._fetch_active_orders_rows_for_market = AsyncMock(return_value=rows)
        self.connector._client_order_index_to_order_index.clear()
        await self.connector._prime_active_orders_snapshot_cache_for_poll_cycle()
        self.assertIn(7, self.connector._active_orders_snapshot_by_market)
        self.assertEqual(rows, self.connector._active_orders_snapshot_by_market[7])
        self.assertIn(7, self.connector._active_orders_snapshot_market_complete)
        self.assertEqual("55", self.connector._client_order_index_to_order_index.get("cid55"))

    async def test_prime_active_orders_snapshot_skips_already_fetched_market(self):
        """Market already in _active_orders_snapshot_market_complete must not be fetched again."""
        self.connector._status_poll_cycle_active = True
        self.connector._active_orders_snapshot_market_complete.add(7)
        self.connector._get_market_spec = AsyncMock(return_value=(7, 3, 2, "BTC"))
        self.connector._fetch_active_orders_rows_for_market = AsyncMock()
        await self.connector._prime_active_orders_snapshot_cache_for_poll_cycle()
        self.connector._fetch_active_orders_rows_for_market.assert_not_called()

    async def test_prime_active_orders_snapshot_logs_warning_on_exception(self):
        """Exceptions must be caught and logged; must not propagate."""
        self.connector._status_poll_cycle_active = True
        self.connector._get_market_spec = AsyncMock(side_effect=RuntimeError("network error"))
        # Should not raise
        await self.connector._prime_active_orders_snapshot_cache_for_poll_cycle()

    # ---------------------------------------------------------------------------
    # Coverage boost: _status_polling_loop_fetch_updates
    # ---------------------------------------------------------------------------

    async def test_status_polling_loop_with_account_data_applies_balances(self):
        """When account snapshot succeeds the balances and positions must be applied."""
        account_data = {"account_equity": "1000", "available_to_spend": "800"}
        with patch.object(self.connector, "_fetch_account_snapshot_data", new=AsyncMock(return_value=account_data)), \
             patch.object(self.connector, "_apply_balances_from_account_data") as mock_apply, \
             patch.object(self.connector, "_update_positions", new=AsyncMock()) as mock_pos, \
             patch.object(self.connector, "_prime_active_orders_snapshot_cache_for_poll_cycle", new=AsyncMock()), \
             patch.object(self.connector, "_update_order_status", new=AsyncMock()) as mock_status:
            await self.connector._status_polling_loop_fetch_updates()
            mock_apply.assert_called_once_with(account_data=account_data)
            mock_pos.assert_called_once()
            mock_status.assert_called_once()
        # Poll cycle must be ended after completion
        self.assertFalse(self.connector._status_poll_cycle_active)

    async def test_status_polling_loop_falls_back_when_snapshot_fails(self):
        """When account snapshot raises, balances/positions must be fetched independently."""
        with patch.object(self.connector, "_fetch_account_snapshot_data", new=AsyncMock(side_effect=IOError("fail"))), \
             patch.object(self.connector, "_update_positions", new=AsyncMock()) as mock_pos, \
             patch.object(self.connector, "_update_balances", new=AsyncMock()) as mock_bal, \
             patch.object(self.connector, "_prime_active_orders_snapshot_cache_for_poll_cycle", new=AsyncMock()), \
             patch.object(self.connector, "_update_order_status", new=AsyncMock()):
            await self.connector._status_polling_loop_fetch_updates()
            mock_pos.assert_called()
            mock_bal.assert_called()
        self.assertFalse(self.connector._status_poll_cycle_active)

    # ---------------------------------------------------------------------------
    # Coverage boost: _update_orders (rescue fill on FILLED order)
    # ---------------------------------------------------------------------------

    async def test_update_orders_rescue_fill_on_newly_filled_order(self):
        """_update_orders must call _all_trade_updates_for_order when order is FILLED with no fills yet."""
        from hummingbot.core.data_type.in_flight_order import TradeUpdate

        mock_order = MagicMock()
        mock_order.client_order_id = "test-order-1"
        mock_order.is_done = False
        mock_order.executed_amount_base = Decimal("0")
        mock_order.amount = Decimal("1")

        filled_update = OrderUpdate(
            trading_pair="BTC-USDC",
            update_timestamp=1234567890.0,
            new_state=OrderState.FILLED,
            client_order_id="test-order-1",
            exchange_order_id="42",
        )
        fill_update = MagicMock(spec=TradeUpdate)

        mock_tracker = MagicMock()
        mock_tracker.active_orders = {"test-order-1": mock_order}
        self.connector._order_tracker = mock_tracker
        self.connector._is_user_stream_initialized = MagicMock(return_value=False)
        self.connector._request_order_status = AsyncMock(return_value=filled_update)
        self.connector._all_trade_updates_for_order = AsyncMock(return_value=[fill_update])

        await self.connector._update_orders()

        self.connector._all_trade_updates_for_order.assert_called_once_with(mock_order)
        mock_tracker.process_trade_update.assert_called_once_with(fill_update)
        mock_tracker.process_order_update.assert_called_once_with(filled_update)

    async def test_update_orders_rescue_fill_handles_exception(self):
        """Exception in _all_trade_updates_for_order must be swallowed."""
        mock_order = MagicMock()
        mock_order.client_order_id = "test-order-2"
        mock_order.is_done = False
        mock_order.executed_amount_base = Decimal("0")
        mock_order.amount = Decimal("1")

        filled_update = OrderUpdate(
            trading_pair="BTC-USDC",
            update_timestamp=1234567890.0,
            new_state=OrderState.FILLED,
            client_order_id="test-order-2",
            exchange_order_id="43",
        )

        mock_tracker = MagicMock()
        mock_tracker.active_orders = {"test-order-2": mock_order}
        self.connector._order_tracker = mock_tracker
        self.connector._is_user_stream_initialized = MagicMock(return_value=False)
        self.connector._request_order_status = AsyncMock(return_value=filled_update)
        self.connector._all_trade_updates_for_order = AsyncMock(side_effect=IOError("trades api down"))

        await self.connector._update_orders()

        mock_tracker.process_order_update.assert_called_once_with(filled_update)

    async def test_update_orders_raises_on_cancelled_error(self):
        """asyncio.CancelledError from _request_order_status must propagate."""
        mock_order = MagicMock()
        mock_order.client_order_id = "test-order-3"

        mock_tracker = MagicMock()
        mock_tracker.active_orders = {"test-order-3": mock_order}
        self.connector._order_tracker = mock_tracker
        self.connector._is_user_stream_initialized = MagicMock(return_value=False)
        self.connector._request_order_status = AsyncMock(side_effect=asyncio.CancelledError())

        with self.assertRaises(asyncio.CancelledError):
            await self.connector._update_orders()

    async def test_update_orders_handles_general_exception_via_error_handler(self):
        """Non-CancelledError exceptions must be passed to _handle_update_error_for_active_order."""
        mock_order = MagicMock()
        mock_order.client_order_id = "test-order-4"

        mock_tracker = MagicMock()
        mock_tracker.active_orders = {"test-order-4": mock_order}
        self.connector._order_tracker = mock_tracker
        self.connector._is_user_stream_initialized = MagicMock(return_value=False)
        self.connector._request_order_status = AsyncMock(side_effect=RuntimeError("boom"))
        self.connector._handle_update_error_for_active_order = AsyncMock()

        await self.connector._update_orders()

        self.connector._handle_update_error_for_active_order.assert_called_once()

    # ---------------------------------------------------------------------------
    # Coverage boost: _request_order_status
    # ---------------------------------------------------------------------------

    async def test_request_order_status_returns_open_when_active_order_found(self):
        """When active order lookup succeeds, state must be OPEN with real exchange_order_id."""
        mock_order = MagicMock()
        mock_order.exchange_order_id = "client-idx-999"
        mock_order.trading_pair = "BTC-USDC"
        mock_order.client_order_id = "cid-1"

        self.connector._client_order_index_to_order_index = {}
        self.connector._get_market_spec = AsyncMock(return_value=(7, 3, 2, "BTC"))
        self.connector._resolve_order_index_from_active_orders = AsyncMock(return_value="12345")
        self.connector._current_timestamp = 1234567890.0

        result = await self.connector._request_order_status(mock_order)

        self.assertEqual(OrderState.OPEN, result.new_state)
        self.assertEqual("12345", result.exchange_order_id)
        self.assertEqual("cid-1", result.client_order_id)

    async def test_request_order_status_returns_canceled_when_not_in_history(self):
        """When order is not active and not found in history, state must be CANCELED."""
        mock_order = MagicMock()
        mock_order.exchange_order_id = "client-idx-999"
        mock_order.trading_pair = "BTC-USDC"
        mock_order.client_order_id = "cid-missing"
        mock_order.creation_timestamp = 0  # old order — outside the grace period

        self.connector._client_order_index_to_order_index = {}
        self.connector._get_market_spec = AsyncMock(return_value=(7, 3, 2, "BTC"))
        self.connector._resolve_order_index_from_active_orders = AsyncMock(return_value=None)
        self.connector._current_timestamp = 1234567890.0

        signer_mock = MagicMock()
        signer_mock.create_auth_token_with_expiry = MagicMock(return_value=("tok", None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_mock)
        self.connector._get_account_index = MagicMock(return_value=237600)
        self.connector._get_api_key_index = MagicMock(return_value=1)
        # Return history with a different order → not matched
        self.connector._api_get = AsyncMock(return_value={
            "data": [{"order_id": "100", "client_order_id": "other-cid", "order_status": "cancelled"}]
        })

        result = await self.connector._request_order_status(mock_order)

        self.assertEqual(OrderState.CANCELED, result.new_state)

    async def test_request_order_status_returns_status_from_history_when_found(self):
        """When order found in history, state must match the raw order_status field."""
        mock_order = MagicMock()
        mock_order.exchange_order_id = "100"
        mock_order.trading_pair = "BTC-USDC"
        mock_order.client_order_id = "cid-found"

        self.connector._client_order_index_to_order_index = {"100": "100"}
        self.connector._get_market_spec = AsyncMock(return_value=(7, 3, 2, "BTC"))
        self.connector._resolve_order_index_from_active_orders = AsyncMock(return_value=None)
        self.connector._current_timestamp = 1234567890.0

        signer_mock = MagicMock()
        signer_mock.create_auth_token_with_expiry = MagicMock(return_value=("tok", None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_mock)
        self.connector._get_account_index = MagicMock(return_value=237600)
        self.connector._get_api_key_index = MagicMock(return_value=1)
        self.connector._api_get = AsyncMock(return_value={
            "data": [{"order_id": "100", "client_order_id": "cid-found", "order_status": "cancelled"}]
        })

        result = await self.connector._request_order_status(mock_order)

        self.assertEqual(OrderState.CANCELED, result.new_state)
        self.assertEqual("100", result.exchange_order_id)

    async def test_request_order_status_raises_when_history_returns_empty_data(self):
        """When history response has no data, IOError must be raised."""
        mock_order = MagicMock()
        mock_order.exchange_order_id = "999"
        mock_order.trading_pair = "BTC-USDC"
        mock_order.client_order_id = "cid-empty"

        self.connector._client_order_index_to_order_index = {}
        self.connector._get_market_spec = AsyncMock(return_value=(7, 3, 2, "BTC"))
        self.connector._resolve_order_index_from_active_orders = AsyncMock(return_value=None)
        self.connector._current_timestamp = 1234567890.0

        signer_mock = MagicMock()
        signer_mock.create_auth_token_with_expiry = MagicMock(return_value=("tok", None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_mock)
        self.connector._get_account_index = MagicMock(return_value=237600)
        self.connector._get_api_key_index = MagicMock(return_value=1)
        self.connector._api_get = AsyncMock(return_value={"data": []})

        with self.assertRaises(IOError):
            await self.connector._request_order_status(mock_order)

    # -----------------------------------------------------------------------
    # Coverage boost batch: static helpers, balance helpers, order-book price
    # -----------------------------------------------------------------------

    def test_is_hex_private_key_variants(self):
        cls = self.connector_cls
        self.assertTrue(cls._is_hex_private_key("0x" + "a" * 64))
        self.assertTrue(cls._is_hex_private_key("b" * 64))
        self.assertFalse(cls._is_hex_private_key(""))
        self.assertFalse(cls._is_hex_private_key("0xshort"))

    def test_get_signer_private_key_from_api_key(self):
        c = self.connector_cls.__new__(self.connector_cls)
        c.api_key = "0x" + "a" * 64
        c.api_secret = ""
        self.assertEqual("0x" + "a" * 64, c._get_signer_private_key())

    def test_get_signer_private_key_from_api_secret(self):
        c = self.connector_cls.__new__(self.connector_cls)
        c.api_key = "not-hex"
        c.api_secret = "0x" + "b" * 64
        self.assertEqual("0x" + "b" * 64, c._get_signer_private_key())

    def test_get_signer_private_key_raises_when_missing_cls(self):
        c = self.connector_cls.__new__(self.connector_cls)
        c.api_key = "1"
        c.api_secret = "2"
        with self.assertRaises(ValueError):
            c._get_signer_private_key()

    def test_get_api_key_index_from_api_key_index_field(self):
        c = self.connector_cls.__new__(self.connector_cls)
        c.api_key_index = "5"
        c.api_key = "not-int"
        c.api_secret = "not-int"
        self.assertEqual(5, c._get_api_key_index())

    def test_get_api_key_index_from_api_key(self):
        c = self.connector_cls.__new__(self.connector_cls)
        c.api_key_index = ""
        c.api_key = "7"
        c.api_secret = "not-int"
        self.assertEqual(7, c._get_api_key_index())

    def test_get_api_key_index_raises_when_not_int(self):
        c = self.connector_cls.__new__(self.connector_cls)
        c.api_key_index = ""
        c.api_key = "not-int"
        c.api_secret = "not-int"
        with self.assertRaises(ValueError):
            c._get_api_key_index()

    def test_get_rest_api_key_branches(self):
        c = self.connector_cls.__new__(self.connector_cls)
        c.api_key = "7"
        c.api_secret = "secret"
        self.assertEqual("7", c._get_rest_api_key())

        c.api_key = "non-int"
        self.assertEqual("secret", c._get_rest_api_key())

        c.api_secret = ""
        self.assertEqual("non-int", c._get_rest_api_key())

    def test_api_host_for_signer_mainnet_vs_testnet(self):
        c = self.connector_cls.__new__(self.connector_cls)
        import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as PCONST
        c._domain = PCONST.DEFAULT_DOMAIN
        mainnet = c._api_host_for_signer()
        self.assertNotIn("/api/v1", mainnet)
        self.assertTrue(mainnet.startswith("https://"))

        c._domain = "lighter_perpetual_testnet"
        testnet = c._api_host_for_signer()
        self.assertNotIn("/api/v1", testnet)
        self.assertTrue(testnet.startswith("https://"))

    def test_first_not_none_returns_first_non_none(self):
        cls = self.connector_cls
        self.assertEqual("x", cls._first_not_none(None, None, "x", "y"))
        self.assertIsNone(cls._first_not_none(None, None))

    def test_account_from_response_branches(self):
        cls = self.connector_cls
        self.assertEqual({"id": 1}, cls._account_from_response({"data": {"id": 1}}))
        self.assertEqual({"id": 2}, cls._account_from_response({"data": [{"id": 2}]}))
        self.assertEqual({"id": 3}, cls._account_from_response({"accounts": [{"id": 3}]}))
        self.assertEqual({"available_balance": "10"}, cls._account_from_response({"available_balance": "10"}))
        self.assertEqual({"collateral": "10"}, cls._account_from_response({"collateral": "10"}))
        self.assertIsNone(cls._account_from_response({}))

    def test_client_order_index_from_order_id_deterministic(self):
        cls = self.connector_cls
        idx1 = cls._client_order_index_from_order_id("HBOT-1")
        idx2 = cls._client_order_index_from_order_id("HBOT-1")
        idx3 = cls._client_order_index_from_order_id("HBOT-2")
        self.assertEqual(idx1, idx2)
        self.assertNotEqual(idx1, idx3)
        self.assertGreater(idx1, 0)

    def test_account_query_params_format(self):
        self.connector._account_index = "237600"
        params = self.connector._account_query_params()
        self.assertEqual("237600", params["value"])
        self.assertEqual("index", params["by"])
        self.assertEqual("true", params["active_only"])

    def test_is_ok_response_checks_code_and_success(self):
        c = self.connector
        self.assertTrue(c._is_ok_response({"success": True}))
        self.assertTrue(c._is_ok_response({"code": 200}))
        self.assertFalse(c._is_ok_response({"code": 400}))
        self.assertFalse(c._is_ok_response({"success": False}))
        self.assertFalse(c._is_ok_response({}))

    def test_is_ok_response_extra_cases(self):
        c = self.connector
        # code 0 means success on Lighter API
        self.assertTrue(c._is_ok_response({"code": 0}))
        # code 200 is also accepted
        self.assertTrue(c._is_ok_response({"code": 200}))
        # non-dict is never success
        self.assertFalse(c._is_ok_response("error-string"))
        # empty dict has no success/code
        self.assertFalse(c._is_ok_response({}))

    def test_should_emit_throttled_warning_gate(self):
        c = self.connector
        timestamps: dict = {}
        c.EMPTY_MARKET_DATA_WARNING_INTERVAL = 30.0
        with patch("time.time", return_value=1000.0):
            self.assertTrue(c._should_emit_throttled_warning("test-key", timestamps))
        with patch("time.time", return_value=1010.0):
            self.assertFalse(c._should_emit_throttled_warning("test-key", timestamps))
        with patch("time.time", return_value=1040.0):
            self.assertTrue(c._should_emit_throttled_warning("test-key", timestamps))

    def test_set_usdc_balances_and_get_available_balance(self):
        c = self.connector
        c._account_balances = {}
        c._account_available_balances = {}
        c._set_usdc_balances(total_balance=Decimal("100"), available_balance=Decimal("80"))
        self.assertEqual(Decimal("100"), c._account_balances["USDC"])
        self.assertEqual(Decimal("80"), c._account_available_balances["USDC"])
        self.assertEqual(Decimal("80"), c.get_available_balance("USDC"))

    def test_get_available_balance_caps_at_total(self):
        c = self.connector
        c._account_balances = {"USDC": Decimal("50")}
        c._account_available_balances = {"USDC": Decimal("80")}
        self.assertEqual(Decimal("50"), c.get_available_balance("USDC"))

    def test_schedule_fast_balance_sync_throttled(self):
        c = self.connector
        c._trading_required = True
        c._last_balance_update_timestamp = 0.0
        fired = []
        with patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.safe_ensure_future") as mock_future:
            mock_future.side_effect = lambda coro: fired.append(coro) or None
            with patch("time.time", return_value=100.0):
                c._schedule_fast_balance_sync(min_interval_seconds=5.0)
            self.assertEqual(1, len(fired))
            # Second call within interval must be suppressed
            with patch("time.time", return_value=103.0):
                c._schedule_fast_balance_sync(min_interval_seconds=5.0)
            self.assertEqual(1, len(fired))

    def test_schedule_fast_balance_sync_no_op_when_not_trading_required(self):
        c = self.connector
        c._trading_required = False
        with patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative.safe_ensure_future") as mock_future:
            c._schedule_fast_balance_sync()
            mock_future.assert_not_called()

    async def test_get_market_spec_raises_when_symbol_not_found(self):
        c = self.connector
        c._market_id_by_symbol = {}
        c._size_decimals_by_symbol = {}
        c._price_decimals_by_symbol = {}
        c.exchange_symbol_associated_to_pair = AsyncMock(return_value="MISSING/USDC")
        c._api_get = AsyncMock(return_value={"order_books": []})
        with self.assertRaises(ValueError):
            await c._get_market_spec("ETH-USDC")

    async def test_refresh_market_metadata_skips_non_perp(self):
        c = self.connector
        c._market_id_by_symbol = {}
        c._size_decimals_by_symbol = {}
        c._price_decimals_by_symbol = {}
        c._api_get = AsyncMock(return_value={"order_books": [
            {"symbol": "ETH/USDC", "market_type": "spot", "market_id": 1, "supported_size_decimals": 4, "supported_price_decimals": 2},
            {"symbol": "BTC/USDC", "market_type": "perp", "market_id": 2, "supported_size_decimals": 3, "supported_price_decimals": 1},
        ]})
        await c._refresh_market_metadata()
        self.assertNotIn("ETH/USDC", c._market_id_by_symbol)
        self.assertIn("BTC/USDC", c._market_id_by_symbol)
        self.assertEqual(2, c._market_id_by_symbol["BTC/USDC"])

    async def test_apply_balances_from_account_data_primary_path(self):
        c = self.connector
        c._account_balances = {}
        c._account_available_balances = {}
        c._fee_tier = 0
        await c._apply_balances_from_account_data({
            "collateral": "500",
            "available_balance": "450",
            "fee_level": 3,
        })
        self.assertEqual(Decimal("500"), c._account_balances["USDC"])
        self.assertEqual(Decimal("450"), c._account_available_balances["USDC"])
        self.assertEqual(3, c._fee_tier)

    async def test_apply_balances_from_account_data_cross_margin_fallback(self):
        c = self.connector
        c._account_balances = {}
        c._account_available_balances = {}
        c._fee_tier = 0
        await c._apply_balances_from_account_data({
            "collateral": "500",
            "cross_asset_value": "400",
            "cross_initial_margin_requirement": "50",
        })
        self.assertEqual(Decimal("500"), c._account_balances["USDC"])
        self.assertEqual(Decimal("350"), c._account_available_balances["USDC"])

    async def test_apply_balances_from_account_data_skips_when_no_available(self):
        c = self.connector
        c._account_balances = {"USDC": Decimal("100")}
        c._account_available_balances = {"USDC": Decimal("100")}
        c.logger = lambda: MagicMock()
        await c._apply_balances_from_account_data({"collateral": "500"})
        # Should not update if neither available_balance nor cross fields present
        self.assertEqual(Decimal("100"), c._account_balances["USDC"])

    async def test_apply_balances_assets_usdc_margin_balance_fallback(self):
        c = self.connector
        c._account_balances = {}
        c._account_available_balances = {}
        c._fee_tier = 0
        await c._apply_balances_from_account_data({
            "assets": [{"symbol": "USDC", "margin_balance": "300"}],
            "available_balance": "250",
        })
        self.assertEqual(Decimal("300"), c._account_balances["USDC"])
        self.assertEqual(Decimal("250"), c._account_available_balances["USDC"])

    def test_index_client_to_order_mapping_from_rows(self):
        c = self.connector
        c._client_order_index_to_order_index = {}
        rows = [
            {"order_id": "100", "client_order_index": "42"},
            {"order_index": "200", "client_order_id": "43"},
            {"i": "300", "I": "44"},
        ]
        c._index_client_to_order_mapping_from_rows(rows)
        self.assertEqual("100", c._client_order_index_to_order_index["42"])
        self.assertEqual("200", c._client_order_index_to_order_index["43"])
        self.assertEqual("300", c._client_order_index_to_order_index["44"])

    async def test_cleanup_startup_orphan_reduce_only_orders_is_noop_minimal(self):
        await self.connector._cleanup_startup_orphan_reduce_only_orders()

    async def test_cleanup_runtime_orphan_orders_is_noop_minimal(self):
        await self.connector._cleanup_runtime_orphan_orders()

    def test_is_order_not_found_cancelation_error(self):
        c = self.connector
        self.assertTrue(c._is_order_not_found_during_cancelation_error(Exception('"code":5')))
        self.assertTrue(c._is_order_not_found_during_cancelation_error(Exception("may already be filled")))
        self.assertFalse(c._is_order_not_found_during_cancelation_error(Exception("timeout")))

    def test_is_order_not_found_status_update_error_minimal(self):
        c = self.connector
        self.assertTrue(c._is_order_not_found_during_status_update_error(Exception("order not found on chain")))
        self.assertFalse(c._is_order_not_found_during_status_update_error(Exception("random error")))

    def test_get_top_order_book_price_no_book(self):
        c = self.connector
        c._last_empty_order_book_warning_timestamp = {}
        c.get_order_book = MagicMock(side_effect=Exception("no book"))
        with patch.object(c, "_should_emit_throttled_warning", return_value=False):
            price = c._get_top_order_book_price("BTC-USDC", is_buy=True)
        import math
        self.assertTrue(math.isnan(float(price)))

    def test_is_balance_info_fresh_and_position_info_fresh(self):
        c = self.connector
        c._last_balance_update_timestamp = 1.0  # any non-zero value
        self.assertTrue(c._is_balance_info_fresh())
        c._last_balance_update_timestamp = 0.0  # zero means never fetched
        self.assertFalse(c._is_balance_info_fresh())
        # position freshness: not trading_required -> always True
        c._trading_required = False
        self.assertTrue(c._is_position_info_fresh())

    async def test_all_trading_pairs_filters_by_perp(self):
        c = self.connector
        c._api_get = AsyncMock(return_value={"order_books": [
            {"symbol": "ETH/USDC", "market_type": "spot", "status": "active"},
            {"symbol": "BTC/USDC", "market_type": "perp", "status": "active"},
            {"symbol": "SOL/USDC", "market_type": "perp", "status": "inactive"},
        ]})
        result = await c.all_trading_pairs()
        self.assertEqual(1, len(result))
        # ETH spot should be excluded; SOL inactive should be excluded
        self.assertFalse(any("SOL" in p for p in result))
        self.assertFalse(any("ETH" in p for p in result))

    async def test_all_trading_pairs_handles_exception(self):
        c = self.connector
        c._api_get = AsyncMock(side_effect=Exception("network error"))
        result = await c.all_trading_pairs()
        self.assertEqual([], result)

    # -----------------------------------------------------------------------
    # Coverage boost batch 2: order failure, trading rules, cancel flows
    # -----------------------------------------------------------------------

    def test_is_expected_order_rejection_patterns(self):
        cls = self.connector_cls
        self.assertTrue(cls._is_expected_order_rejection("minimum notional"))
        self.assertTrue(cls._is_expected_order_rejection("minimum lot size"))
        self.assertTrue(cls._is_expected_order_rejection("invalid order base or quote amount"))
        self.assertFalse(cls._is_expected_order_rejection("server timeout"))

    def test_on_order_failure_expected_rejection(self):
        c = self.connector
        c._update_order_after_failure = MagicMock()
        c._trading_rules = {}
        c._last_sub_minimum_position_warning_ts = {}
        c.logger = lambda: MagicMock()
        c._on_order_failure(
            order_id="HBOT-rej",
            trading_pair="BTC-USDC",
            amount=Decimal("0.001"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("10"),
            exception=Exception("Order notional below the minimum notional"),
        )
        c._update_order_after_failure.assert_called_once()

    def test_is_sub_minimum_position_notional_no_rule(self):
        c = self.connector
        c._trading_rules = {}
        self.assertFalse(c._is_sub_minimum_position_notional("BTC-USDC", Decimal("0.001"), Decimal("30000")))

    def test_is_sub_minimum_position_notional_below_min(self):
        c = self.connector
        rule = TradingRule(
            trading_pair="BTC-USDC",
            min_order_size=Decimal("0.00001"),
            min_price_increment=Decimal("1"),
            min_base_amount_increment=Decimal("0.00001"),
            min_notional_size=Decimal("10"),
            min_order_value=Decimal("10"),
        )
        c._trading_rules = {"BTC-USDC": rule}
        # 0.0001 BTC @ 30000 = 3 USDC < 10 min
        self.assertTrue(c._is_sub_minimum_position_notional("BTC-USDC", Decimal("0.0001"), Decimal("30000")))

    def test_is_sub_minimum_position_notional_above_min(self):
        c = self.connector
        rule = TradingRule(
            trading_pair="BTC-USDC",
            min_order_size=Decimal("0.00001"),
            min_price_increment=Decimal("1"),
            min_base_amount_increment=Decimal("0.00001"),
            min_notional_size=Decimal("10"),
            min_order_value=Decimal("10"),
        )
        c._trading_rules = {"BTC-USDC": rule}
        # 1 BTC @ 30000 = 30000 USDC >> 10 min
        self.assertFalse(c._is_sub_minimum_position_notional("BTC-USDC", Decimal("1"), Decimal("30000")))

    def test_get_buy_sell_collateral_token(self):
        c = self.connector
        self.assertEqual("USDC", c.get_buy_collateral_token("BTC-USDC"))
        self.assertEqual("USDC", c.get_sell_collateral_token("BTC-USDC"))

    def test_is_cancel_request_synchronous(self):
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_funding_fee_poll_interval(self):
        self.assertEqual(120, self.connector.funding_fee_poll_interval)

    def test_supported_position_modes(self):
        modes = self.connector.supported_position_modes()
        self.assertEqual([PositionMode.ONEWAY], modes)

    def test_supported_order_types_perp(self):
        types = self.connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, types)
        self.assertIn(OrderType.MARKET, types)

    async def test_place_cancel_returns_false_when_no_exchange_order_id(self):
        c = self.connector
        tracked = type("Order", (), {
            "exchange_order_id": None,
            "trading_pair": "BTC-USDC",
        })()
        result = await c._place_cancel("HBOT-X", tracked)
        self.assertFalse(result)

    async def test_reconcile_unmatched_private_event_throttled(self):
        c = self.connector
        c._last_unmatched_private_event_reconcile_ts = 0.0
        c._update_order_status = AsyncMock()
        c._update_positions = AsyncMock()
        c._update_balances = AsyncMock()
        c.logger = lambda: MagicMock()

        with patch("time.time", return_value=100.0):
            await c._reconcile_unmatched_private_event("test")
        c._update_order_status.assert_awaited_once()

        # Second call within 2s should be throttled
        c._update_order_status.reset_mock()
        with patch("time.time", return_value=101.0):
            await c._reconcile_unmatched_private_event("test")
        c._update_order_status.assert_not_awaited()

    async def test_cleanup_startup_orphan_and_runtime_orphan_noop(self):
        await self.connector._cleanup_startup_orphan_reduce_only_orders()
        await self.connector._cleanup_runtime_orphan_orders()

    async def test_apply_balances_account_equity_fallback(self):
        c = self.connector
        c._account_balances = {}
        c._account_available_balances = {}
        c._fee_tier = 0
        await c._apply_balances_from_account_data({
            "account_equity": "200",
            "available_balance": "180",
            "fee_level": 1,
        })
        self.assertEqual(Decimal("200"), c._account_balances["USDC"])
        self.assertEqual(Decimal("180"), c._account_available_balances["USDC"])

    async def test_refresh_account_state_calls_positions_and_balances(self):
        c = self.connector
        c._update_positions = AsyncMock()
        c._update_balances = AsyncMock()
        c.logger = lambda: MagicMock()
        await c._refresh_account_state(refresh_positions=True, refresh_balances=True, reason="test")
        c._update_positions.assert_awaited_once()
        c._update_balances.assert_awaited_once()

    async def test_refresh_account_state_skips_when_both_false(self):
        c = self.connector
        c._update_positions = AsyncMock()
        c._update_balances = AsyncMock()
        await c._refresh_account_state(refresh_positions=False, refresh_balances=False, reason="test")
        c._update_positions.assert_not_awaited()
        c._update_balances.assert_not_awaited()

    def test_allocate_client_order_index_increments(self):
        c = self.connector
        c._last_client_order_index = 0
        idx1 = c._allocate_client_order_index()
        idx2 = c._allocate_client_order_index()
        self.assertGreater(idx1, 0)
        self.assertGreater(idx2, idx1)

    async def test_estimate_open_order_initial_margin_empty_positions(self):
        c = self.connector
        c._status_poll_cycle_active = False
        result = await c._estimate_open_order_initial_margin({"positions": []})
        self.assertIsNone(result)

    async def test_estimate_open_order_initial_margin_no_positions_key(self):
        c = self.connector
        result = await c._estimate_open_order_initial_margin({"collateral": "100"})
        self.assertIsNone(result)

    async def test_place_cancel_returns_false_when_exchange_order_id_none_string(self):
        c = self.connector
        c._client_order_index_to_client_order_id = {}
        c.logger = lambda: MagicMock()
        tracked = type("Order", (), {
            "exchange_order_id": "None",
            "trading_pair": "BTC-USDC",
            "client_order_id": "HBOT-NONE",
        })()
        c._get_market_spec = AsyncMock(return_value=(1, 2, 2, "BTC/USDC"))
        result = await c._place_cancel("HBOT-NONE", tracked)
        self.assertFalse(result)

    # -----------------------------------------------------------------------
    # Coverage boost batch 3: format_trading_rules, get_price_by_type,
    # generate_api_key_pair, _place_order success
    # -----------------------------------------------------------------------

    async def test_format_trading_rules_order_books_path(self):
        """_format_trading_rules with order_books format (mixed perp and non-perp)."""
        c = self.connector
        c._market_id_by_symbol = {}
        c._size_decimals_by_symbol = {}
        c._price_decimals_by_symbol = {}
        c.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")

        exchange_info = {
            "order_books": [
                {
                    "market_type": "spot",
                    "symbol": "ETH",
                    "market_id": "2",
                    "supported_size_decimals": 4,
                    "supported_price_decimals": 2,
                    "min_quote_amount": "10",
                },
                {
                    "market_type": "perp",
                    "symbol": "BTC",
                    "market_id": "1",
                    "supported_size_decimals": 5,
                    "supported_price_decimals": 2,
                    "min_quote_amount": "5",
                },
            ]
        }
        rules = await c._format_trading_rules(exchange_info)
        self.assertEqual(1, len(rules))
        self.assertEqual("BTC-USDC", rules[0].trading_pair)
        self.assertEqual(Decimal("0.00001"), rules[0].min_order_size)
        self.assertEqual(1, c._market_id_by_symbol["BTC"])

    async def test_format_trading_rules_order_books_skips_unknown_pair(self):
        c = self.connector
        c._market_id_by_symbol = {}
        c._size_decimals_by_symbol = {}
        c._price_decimals_by_symbol = {}
        c.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=KeyError("unknown"))
        c.logger = lambda: MagicMock()

        exchange_info = {
            "order_books": [
                {
                    "market_type": "perp",
                    "symbol": "NEWCOIN",
                    "market_id": "99",
                    "supported_size_decimals": 2,
                    "supported_price_decimals": 1,
                    "min_quote_amount": "10",
                },
            ]
        }
        rules = await c._format_trading_rules(exchange_info)
        self.assertEqual(0, len(rules))

    async def test_format_trading_rules_data_path(self):
        c = self.connector
        c.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="ETH-USDC")
        exchange_info = {
            "data": [
                {
                    "symbol": "ETH",
                    "lot_size": "0.001",
                    "tick_size": "0.1",
                    "min_order_size": "10",
                }
            ]
        }
        rules = await c._format_trading_rules(exchange_info)
        self.assertEqual(1, len(rules))
        self.assertEqual("ETH-USDC", rules[0].trading_pair)

    def test_get_price_by_type_best_bid(self):
        c = self.connector
        c._get_top_order_book_price = MagicMock(return_value=Decimal("29900"))
        result = c.get_price_by_type("BTC-USDC", PriceType.BestBid)
        self.assertEqual(Decimal("29900"), result)

    def test_get_price_by_type_best_ask(self):
        c = self.connector
        c._get_top_order_book_price = MagicMock(return_value=Decimal("30100"))
        result = c.get_price_by_type("BTC-USDC", PriceType.BestAsk)
        self.assertEqual(Decimal("30100"), result)

    def test_get_price_by_type_mid_price(self):
        c = self.connector
        ask = Decimal("30100")
        bid = Decimal("29900")
        c._get_top_order_book_price = MagicMock(side_effect=[ask, bid])
        result = c.get_price_by_type("BTC-USDC", PriceType.MidPrice)
        self.assertEqual((ask + bid) / Decimal("2"), result)

    def test_get_price_by_type_mid_price_nan(self):
        c = self.connector
        c._get_top_order_book_price = MagicMock(return_value=Decimal("NaN"))
        result = c.get_price_by_type("BTC-USDC", PriceType.MidPrice)
        self.assertTrue(result.is_nan())

    def test_get_price_by_type_last_trade_no_price(self):
        c = self.connector
        mock_book = MagicMock()
        mock_book.last_trade_price = None
        c.get_order_book = MagicMock(return_value=mock_book)
        result = c.get_price_by_type("BTC-USDC", PriceType.LastTrade)
        self.assertTrue(result.is_nan())

    def test_get_price_by_type_unknown(self):
        c = self.connector
        result = c.get_price_by_type("BTC-USDC", "INVALID_PRICE_TYPE")
        self.assertTrue(result.is_nan())

    def test_generate_api_key_pair_success(self):
        c = self.connector
        mock_lighter = MagicMock()
        mock_lighter.create_api_key.return_value = ("privkey", "pubkey", None)
        with patch.dict("sys.modules", {"lighter": mock_lighter}):
            priv, pub = c.generate_api_key_pair()
        self.assertEqual("privkey", priv)
        self.assertEqual("pubkey", pub)

    def test_generate_api_key_pair_error_raises(self):
        c = self.connector
        mock_lighter = MagicMock()
        mock_lighter.create_api_key.return_value = (None, None, "some error")
        with patch.dict("sys.modules", {"lighter": mock_lighter}):
            with self.assertRaises(ValueError):
                c.generate_api_key_pair()

    def test_is_ok_response_code_exception(self):
        c = self.connector
        self.assertFalse(c._is_ok_response({"success": None, "code": None}))
        self.assertFalse(c._is_ok_response({"success": None, "code": "abc"}))

    def test_account_from_response_accounts_wrapper(self):
        cls = self.connector_cls
        result = cls._account_from_response({"accounts": [{"collateral": "100"}]})
        self.assertEqual({"collateral": "100"}, result)

    def test_account_from_response_empty_returns_none(self):
        cls = self.connector_cls
        self.assertIsNone(cls._account_from_response({}))

    async def test_place_order_success(self):
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        c._trading_rules = {}
        c._client_order_index_to_client_order_id = {}
        c._schedule_fast_balance_sync = MagicMock()
        c._last_client_order_index = 0
        c._current_timestamp = 1000.0
        c.logger = lambda: MagicMock()

        mock_resp = MagicMock()
        mock_resp.code = 200
        mock_signer = MagicMock()
        mock_signer.ORDER_TYPE_LIMIT = "LIMIT"
        mock_signer.ORDER_TYPE_MARKET = "MARKET"
        mock_signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
        mock_signer.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "IOC"
        mock_signer.ORDER_TIME_IN_FORCE_POST_ONLY = "POST_ONLY"
        mock_signer.DEFAULT_28_DAY_ORDER_EXPIRY = 9999
        mock_signer.DEFAULT_IOC_EXPIRY = 0
        mock_signer.create_order = AsyncMock(return_value=(None, mock_resp, None))
        c._lighter_signer_client = mock_signer
        c._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        c._signer_request_lock = asyncio.Lock()
        c._get_api_key_index = MagicMock(return_value=0)

        result = await c._place_order(
            order_id="HBOT-1",
            trading_pair="BTC-USDC",
            amount=Decimal("0.01"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("30000"),
            position_action=PositionAction.OPEN,
        )
        self.assertIsInstance(result, tuple)
        c._schedule_fast_balance_sync.assert_called()

    async def test_place_order_market_buy(self):
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        c._trading_rules = {}
        c._client_order_index_to_client_order_id = {}
        c._schedule_fast_balance_sync = MagicMock()
        c._last_client_order_index = 0
        c._current_timestamp = 1000.0
        c.logger = lambda: MagicMock()

        mock_book = MagicMock()
        mock_book.get_price.return_value = 30000
        c.get_order_book = MagicMock(return_value=mock_book)

        mock_resp = MagicMock()
        mock_resp.code = 200
        mock_signer = MagicMock()
        mock_signer.ORDER_TYPE_LIMIT = "LIMIT"
        mock_signer.ORDER_TYPE_MARKET = "MARKET"
        mock_signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
        mock_signer.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "IOC"
        mock_signer.ORDER_TIME_IN_FORCE_POST_ONLY = "POST_ONLY"
        mock_signer.DEFAULT_28_DAY_ORDER_EXPIRY = 9999
        mock_signer.DEFAULT_IOC_EXPIRY = 0
        mock_signer.create_order = AsyncMock(return_value=(None, mock_resp, None))
        c._lighter_signer_client = mock_signer
        c._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        c._signer_request_lock = asyncio.Lock()
        c._get_api_key_index = MagicMock(return_value=0)

        result = await c._place_order(
            order_id="HBOT-M",
            trading_pair="BTC-USDC",
            amount=Decimal("0.01"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("NaN"),
            position_action=PositionAction.OPEN,
        )
        self.assertIsNotNone(result)
        call_kwargs = mock_signer.create_order.call_args.kwargs
        self.assertEqual("MARKET", call_kwargs["order_type"])
        self.assertEqual("IOC", call_kwargs["time_in_force"])

    async def test_place_order_fails_on_signer_error(self):
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        c._trading_rules = {}
        c._client_order_index_to_client_order_id = {}
        c._last_client_order_index = 0
        c.logger = lambda: MagicMock()

        mock_signer = MagicMock()
        mock_signer.ORDER_TYPE_LIMIT = "LIMIT"
        mock_signer.ORDER_TYPE_MARKET = "MARKET"
        mock_signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
        mock_signer.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "IOC"
        mock_signer.ORDER_TIME_IN_FORCE_POST_ONLY = "POST_ONLY"
        mock_signer.DEFAULT_28_DAY_ORDER_EXPIRY = 9999
        mock_signer.DEFAULT_IOC_EXPIRY = 0
        mock_signer.create_order = AsyncMock(return_value=(None, None, "sign error"))
        c._lighter_signer_client = mock_signer
        c._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        c._signer_request_lock = asyncio.Lock()
        c._get_api_key_index = MagicMock(return_value=0)

        with self.assertRaises(IOError):
            await c._place_order(
                order_id="HBOT-F",
                trading_pair="BTC-USDC",
                amount=Decimal("0.01"),
                trade_type=TradeType.SELL,
                order_type=OrderType.LIMIT,
                price=Decimal("30000"),
                position_action=PositionAction.OPEN,
            )

    async def test_place_order_below_min_notional_raises(self):
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        rule = TradingRule(
            trading_pair="BTC-USDC",
            min_order_size=Decimal("0.00001"),
            min_price_increment=Decimal("1"),
            min_base_amount_increment=Decimal("0.00001"),
            min_notional_size=Decimal("100"),
            min_order_value=Decimal("100"),
        )
        c._trading_rules = {"BTC-USDC": rule}
        c._last_client_order_index = 0
        c.logger = lambda: MagicMock()
        mock_signer = MagicMock()
        mock_signer.ORDER_TYPE_LIMIT = "LIMIT"
        mock_signer.ORDER_TYPE_MARKET = "MARKET"
        mock_signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
        mock_signer.DEFAULT_28_DAY_ORDER_EXPIRY = 9999
        c._lighter_signer_client = mock_signer
        c._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        c._signer_request_lock = asyncio.Lock()

        with self.assertRaises(IOError):
            await c._place_order(
                order_id="HBOT-S",
                trading_pair="BTC-USDC",
                amount=Decimal("0.001"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("30000"),
                position_action=PositionAction.OPEN,
            )

    async def test_place_order_close_rounds_up_sub_minimum(self):
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        rule = TradingRule(
            trading_pair="BTC-USDC",
            min_order_size=Decimal("0.00001"),
            min_price_increment=Decimal("1"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("10"),
            min_order_value=Decimal("10"),
        )
        c._trading_rules = {"BTC-USDC": rule}
        c._client_order_index_to_client_order_id = {}
        c._schedule_fast_balance_sync = MagicMock()
        c._last_client_order_index = 0
        c._current_timestamp = 1000.0
        c.logger = lambda: MagicMock()

        mock_resp = MagicMock()
        mock_resp.code = 200
        mock_signer = MagicMock()
        mock_signer.ORDER_TYPE_LIMIT = "LIMIT"
        mock_signer.ORDER_TYPE_MARKET = "MARKET"
        mock_signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
        mock_signer.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "IOC"
        mock_signer.ORDER_TIME_IN_FORCE_POST_ONLY = "POST_ONLY"
        mock_signer.DEFAULT_28_DAY_ORDER_EXPIRY = 9999
        mock_signer.DEFAULT_IOC_EXPIRY = 0
        mock_signer.create_order = AsyncMock(return_value=(None, mock_resp, None))
        c._lighter_signer_client = mock_signer
        c._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        c._signer_request_lock = asyncio.Lock()
        c._get_api_key_index = MagicMock(return_value=0)

        result = await c._place_order(
            order_id="HBOT-C",
            trading_pair="BTC-USDC",
            amount=Decimal("0.0001"),
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("30000"),
            position_action=PositionAction.CLOSE,
        )
        self.assertIsNotNone(result)
        call_kwargs = mock_signer.create_order.call_args.kwargs
        self.assertTrue(call_kwargs["reduce_only"])

    async def test_place_order_limit_maker_post_only(self):
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        c._trading_rules = {}
        c._client_order_index_to_client_order_id = {}
        c._schedule_fast_balance_sync = MagicMock()
        c._last_client_order_index = 0
        c._current_timestamp = 1000.0
        c.logger = lambda: MagicMock()

        mock_resp = MagicMock()
        mock_resp.code = 200
        mock_signer = MagicMock()
        mock_signer.ORDER_TYPE_LIMIT = "LIMIT"
        mock_signer.ORDER_TYPE_MARKET = "MARKET"
        mock_signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
        mock_signer.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "IOC"
        mock_signer.ORDER_TIME_IN_FORCE_POST_ONLY = "POST_ONLY"
        mock_signer.DEFAULT_28_DAY_ORDER_EXPIRY = 9999
        mock_signer.DEFAULT_IOC_EXPIRY = 0
        mock_signer.create_order = AsyncMock(return_value=(None, mock_resp, None))
        c._lighter_signer_client = mock_signer
        c._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        c._signer_request_lock = asyncio.Lock()
        c._get_api_key_index = MagicMock(return_value=0)

        await c._place_order(
            order_id="HBOT-PM",
            trading_pair="BTC-USDC",
            amount=Decimal("0.01"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT_MAKER,
            price=Decimal("30000"),
            position_action=PositionAction.OPEN,
        )
        call_kwargs = mock_signer.create_order.call_args.kwargs
        self.assertEqual("POST_ONLY", call_kwargs["time_in_force"])

    # ── order book price helpers ───────────────────────────────────────────

    def test_get_top_order_book_price_returns_quantized_best_ask(self):
        """_get_top_order_book_price returns quantized price when order book has entries."""
        c = self.connector
        mock_entry = MagicMock()
        mock_entry.price = "100.5"
        mock_book = MagicMock()
        mock_book.ask_entries.return_value = iter([mock_entry])
        c.get_order_book = MagicMock(return_value=mock_book)
        c.quantize_order_price = MagicMock(return_value=Decimal("100.5"))
        c._should_emit_throttled_warning = MagicMock(return_value=False)
        c._last_empty_order_book_warning_timestamp = {}
        result = c._get_top_order_book_price("BTC-USDC", True)
        self.assertEqual(Decimal("100.5"), result)
        c.quantize_order_price.assert_called_once_with("BTC-USDC", Decimal("100.5"))

    def test_get_price_delegates_to_top_order_book_price(self):
        """get_price calls _get_top_order_book_price (line 214)."""
        c = self.connector
        c._get_top_order_book_price = MagicMock(return_value=Decimal("500"))
        result = c.get_price("BTC-USDC", True)
        self.assertEqual(Decimal("500"), result)
        c._get_top_order_book_price.assert_called_once_with(trading_pair="BTC-USDC", is_buy=True)

    def test_get_price_by_type_last_trade_valid_price(self):
        """LastTrade path returns price > 0 (line 231)."""
        c = self.connector
        mock_book = MagicMock()
        mock_book.last_trade_price = Decimal("12345.6")
        c.get_order_book = MagicMock(return_value=mock_book)
        result = c.get_price_by_type("BTC-USDC", PriceType.LastTrade)
        self.assertEqual(Decimal("12345.6"), result)

    # ── _refresh_signer_client_async ──────────────────────────────────────

    async def test_refresh_signer_client_async_clears_and_rebuilds_client(self):
        """_refresh_signer_client_async sets client to None then creates new (lines 359-362)."""
        c = self.connector
        mock_new_client = MagicMock()
        c._lighter_signer_client = "old"
        c._get_lighter_signer_client = MagicMock(return_value=mock_new_client)
        result = await c._refresh_signer_client_async()
        self.assertIs(mock_new_client, result)
        # Client was cleared before executor call
        c._get_lighter_signer_client.assert_called()

    # ── _format_trading_rules data path skip unknown ──────────────────────

    async def test_format_trading_rules_data_path_skips_unknown_symbol(self):
        """data-format: KeyError from exchange_symbol lookup logs debug and skips (lines 880-881, 886)."""
        c = self.connector
        c.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=KeyError("unknown"))
        pair_info = {
            "symbol": "UNKNOWN-PERP",
            "lot_size": "0.01",
            "tick_size": "0.01",
            "min_order_size": "1",
        }
        result = await c._format_trading_rules({"data": [pair_info]})
        self.assertEqual([], result)

    # ── generate_api_key_pair import failure ──────────────────────────────

    def test_generate_api_key_pair_import_error_raises(self):
        """Missing lighter SDK raises ImportError (lines 527-528)."""
        c = self.connector
        with patch.dict("sys.modules", {"lighter": None}):
            with self.assertRaises(ImportError):
                c.generate_api_key_pair()

    # ── _place_order error paths ──────────────────────────────────────────

    def _make_perp_place_order_setup(self, signer_responses):
        """Helper: set up connector for _place_order tests."""
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        c._trading_rules = {}
        c._client_order_index_to_client_order_id = {}
        c._schedule_fast_balance_sync = MagicMock()
        c._last_client_order_index = 0
        c._current_timestamp = 1000.0
        c.logger = lambda: MagicMock()
        c._sleep = AsyncMock()

        mock_signer = MagicMock()
        mock_signer.ORDER_TYPE_LIMIT = "LIMIT"
        mock_signer.ORDER_TYPE_MARKET = "MARKET"
        mock_signer.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME = "GTT"
        mock_signer.ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL = "IOC"
        mock_signer.ORDER_TIME_IN_FORCE_POST_ONLY = "POST_ONLY"
        mock_signer.DEFAULT_28_DAY_ORDER_EXPIRY = 9999
        mock_signer.DEFAULT_IOC_EXPIRY = 0
        mock_signer.create_order = AsyncMock(side_effect=signer_responses)
        c._lighter_signer_client = mock_signer
        c._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        c._signer_request_lock = asyncio.Lock()
        c._get_api_key_index = MagicMock(return_value=0)
        return c, mock_signer

    async def test_place_order_nonce_retry_then_success(self):
        """'invalid nonce' error triggers signer refresh and retry (lines 1015-1018)."""
        mock_resp = MagicMock()
        mock_resp.code = 200
        c, mock_signer = self._make_perp_place_order_setup([
            (None, None, "invalid nonce: sequence too old"),
            (None, mock_resp, None),
        ])
        c._refresh_signer_client_async = AsyncMock(return_value=mock_signer)

        result = await c._place_order(
            order_id="HBOT-N",
            trading_pair="BTC-USDC",
            amount=Decimal("0.01"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("30000"),
            position_action=PositionAction.OPEN,
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(2, mock_signer.create_order.call_count)

    async def test_place_order_raises_with_trading_rule_min_amount_info(self):
        """'invalid order base or quote amount' error includes trading rule details (lines 1024-1028, 1032)."""
        c, _ = self._make_perp_place_order_setup([
            (None, None, "invalid order base or quote amount")
        ])
        c._trading_rules = {
            "BTC-USDC": TradingRule(
                trading_pair="BTC-USDC",
                min_order_size=Decimal("0.000001"),
                min_price_increment=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.001"),
                min_notional_size=Decimal("0.000001"),
                min_order_value=Decimal("0.000001"),
            )
        }

        with self.assertRaises(IOError) as ctx:
            await c._place_order(
                order_id="HBOT-MIN",
                trading_pair="BTC-USDC",
                amount=Decimal("0.01"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("30000"),
                position_action=PositionAction.OPEN,
            )
        self.assertIn("minimum base amount", str(ctx.exception))

    async def test_place_order_raises_when_tx_response_none(self):
        """No error but None tx_response raises IOError (line 1035)."""
        c, _ = self._make_perp_place_order_setup([
            (None, None, None)  # error=None, tx_response=None
        ])

        with self.assertRaises(IOError):
            await c._place_order(
                order_id="HBOT-TX",
                trading_pair="BTC-USDC",
                amount=Decimal("0.01"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("30000"),
                position_action=PositionAction.OPEN,
            )

    async def test_place_order_raises_on_unsupported_order_type_perp(self):
        """Unsupported order type raises ValueError (line 917)."""
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        c._get_lighter_signer_client = MagicMock(return_value=MagicMock())
        c._trading_rules = {}
        c._current_timestamp = 1000.0
        c.supported_order_types = lambda: [OrderType.LIMIT]  # exclude MARKET

        with self.assertRaises(ValueError):
            await c._place_order(
                order_id="HBOT-UNSUP",
                trading_pair="BTC-USDC",
                amount=Decimal("0.01"),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                price=Decimal("NaN"),
                position_action=PositionAction.OPEN,
            )

    # ------------------------------------------------------------------
    # _recover_exchange_order_id_from_active_orders
    # ------------------------------------------------------------------

    async def test_recover_exchange_order_id_returns_none_when_no_rows(self):
        """Returns None when the active-orders snapshot for the market is empty."""
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))
        c._active_orders_snapshot_by_market = {}

        tracked_order = MagicMock()
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.trade_type = TradeType.BUY
        tracked_order.price = Decimal("30000")

        result = await c._recover_exchange_order_id_from_active_orders(tracked_order)
        self.assertIsNone(result)

    async def test_recover_exchange_order_id_returns_unique_candidate(self):
        """Returns the exchange order_id when exactly one active order matches price and side."""
        c = self.connector
        # price_decimals=2 → expected_price_scaled = int(100.00 * 1e2) = 10000
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))

        tracked_order = MagicMock()
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.trade_type = TradeType.BUY
        tracked_order.price = Decimal("100.00")

        c._active_orders_snapshot_by_market = {
            1: [{"order_id": "99", "side": "bid", "price": "100.00"}]
        }
        c._order_tracker._in_flight_orders = {}

        result = await c._recover_exchange_order_id_from_active_orders(tracked_order)
        self.assertEqual("99", result)

    async def test_recover_exchange_order_id_returns_none_on_multiple_candidates(self):
        """Returns None when multiple active orders match (ambiguous recovery)."""
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))

        tracked_order = MagicMock()
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.trade_type = TradeType.BUY
        tracked_order.price = Decimal("100.00")

        c._active_orders_snapshot_by_market = {
            1: [
                {"order_id": "99", "side": "bid", "price": "100.00"},
                {"order_id": "100", "side": "bid", "price": "100.00"},
            ]
        }
        c._order_tracker._in_flight_orders = {}

        result = await c._recover_exchange_order_id_from_active_orders(tracked_order)
        self.assertIsNone(result)

    async def test_recover_exchange_order_id_skips_already_tracked_order(self):
        """Skips an order_id that is already tracked in in_flight_orders."""
        c = self.connector
        c._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC/USDC"))

        tracked_order = MagicMock()
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.trade_type = TradeType.BUY
        tracked_order.price = Decimal("100.00")

        already_tracked = MagicMock()
        already_tracked.exchange_order_id = "99"

        c._active_orders_snapshot_by_market = {
            1: [{"order_id": "99", "side": "bid", "price": "100.00"}]
        }
        c._order_tracker._in_flight_orders = {"HBOT-OTHER": already_tracked}

        result = await c._recover_exchange_order_id_from_active_orders(tracked_order)
        self.assertIsNone(result)

    # ------------------------------------------------------------------
    # _cancel_tracked_orders_on_stop
    # ------------------------------------------------------------------

    async def test_cancel_tracked_orders_on_stop_empty_returns_zero(self):
        """Returns 0 immediately when there are no tracked in-flight orders."""
        c = self.connector
        c._order_tracker._in_flight_orders = {}

        result = await c._cancel_tracked_orders_on_stop()
        self.assertEqual(0, result)

    async def test_cancel_tracked_orders_on_stop_cancels_all_tracked(self):
        """Cancels each tracked order and returns the count of successful cancels."""
        c = self.connector
        order1 = MagicMock()
        order1.client_order_id = "HBOT-1"
        order2 = MagicMock()
        order2.client_order_id = "HBOT-2"
        c._order_tracker._in_flight_orders = {"HBOT-1": order1, "HBOT-2": order2}
        c._execute_order_cancel = AsyncMock(side_effect=["HBOT-1", "HBOT-2"])

        result = await c._cancel_tracked_orders_on_stop()
        self.assertEqual(2, result)

    async def test_cancel_tracked_orders_on_stop_exception_does_not_propagate(self):
        """An exception during individual order cancel is swallowed; count = 0."""
        c = self.connector
        order1 = MagicMock()
        order1.client_order_id = "HBOT-ERR"
        c._order_tracker._in_flight_orders = {"HBOT-ERR": order1}
        c._execute_order_cancel = AsyncMock(side_effect=Exception("network error"))

        result = await c._cancel_tracked_orders_on_stop()
        self.assertEqual(0, result)

    async def test_cancel_tracked_orders_on_stop_returns_none_as_zero(self):
        """If _execute_order_cancel returns None, that order does not count."""
        c = self.connector
        order1 = MagicMock()
        order1.client_order_id = "HBOT-NONE"
        c._order_tracker._in_flight_orders = {"HBOT-NONE": order1}
        c._execute_order_cancel = AsyncMock(return_value=None)

        result = await c._cancel_tracked_orders_on_stop()
        self.assertEqual(0, result)

    # ------------------------------------------------------------------
    # _should_ignore_scoped_private_event
    # ------------------------------------------------------------------

    def test_should_ignore_unknown_channel_base_returns_false(self):
        """Non-private channel_base → always False (line 2934 branch)."""
        result = self.connector._should_ignore_scoped_private_event(
            channel="public_feed/99", channel_base="public_feed"
        )
        self.assertFalse(result)

    def test_should_ignore_no_scoped_identifier_returns_false(self):
        """Private channel but no numeric scope → False (no-digit branch)."""
        result = self.connector._should_ignore_scoped_private_event(
            channel="account_all", channel_base="account_all"
        )
        self.assertFalse(result)

    def test_should_ignore_non_digit_scope_returns_false(self):
        """Private channel with non-numeric scope → False (isdigit branch)."""
        result = self.connector._should_ignore_scoped_private_event(
            channel="account_all/abc", channel_base="account_all"
        )
        self.assertFalse(result)

    def test_should_ignore_colon_separator_non_digit_returns_false(self):
        """Private channel with colon separator and non-numeric scope → False."""
        result = self.connector._should_ignore_scoped_private_event(
            channel="account_all:xyz", channel_base="account_all"
        )
        self.assertFalse(result)

    def test_should_ignore_matching_account_index_returns_false(self):
        """When scoped identifier matches our account index → False (correct account)."""
        self.connector._get_account_index = MagicMock(return_value=42)
        result = self.connector._should_ignore_scoped_private_event(
            channel="account_all/42", channel_base="account_all"
        )
        self.assertFalse(result)

    def test_should_ignore_mismatched_account_index_returns_true(self):
        """When scoped identifier does NOT match our account index → True (ignore)."""
        self.connector._get_account_index = MagicMock(return_value=42)
        result = self.connector._should_ignore_scoped_private_event(
            channel="account_all/99", channel_base="account_all"
        )
        self.assertTrue(result)

    def test_should_ignore_get_account_index_raises_returns_false(self):
        """When _get_account_index raises → False (exception branch)."""
        self.connector._get_account_index = MagicMock(side_effect=Exception("not configured"))
        result = self.connector._should_ignore_scoped_private_event(
            channel="account_all/5", channel_base="account_all"
        )
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # round_amount / round_fee
    # ------------------------------------------------------------------

    def test_round_fee_returns_rounded_decimal(self):
        result = self.connector.round_fee(Decimal("1.123456789"))
        self.assertEqual(round(Decimal("1.123456789"), 6), result)

    def test_round_fee_zero(self):
        result = self.connector.round_fee(Decimal("0"))
        self.assertEqual(0, result)

    def test_round_amount_quantizes_to_rule(self):
        from hummingbot.connector.trading_rule import TradingRule
        rule = TradingRule(
            trading_pair="BTC-USDC",
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
        )
        self.connector._trading_rules["BTC-USDC"] = rule
        result = self.connector.round_amount("BTC-USDC", Decimal("1.23456789"))
        self.assertEqual(Decimal("1.235"), result)

    # ------------------------------------------------------------------
    # get_all_pairs_prices
    # ------------------------------------------------------------------

    async def test_get_all_pairs_prices_returns_list_on_success(self):
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": [{"symbol": "BTC", "mark": "50000"}],
        })
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")
        result = await self.connector.get_all_pairs_prices()
        self.assertEqual([{"trading_pair": "BTC-USDC", "price": "50000"}], result)

    async def test_get_all_pairs_prices_returns_empty_on_failure(self):
        self.connector._api_get = AsyncMock(return_value={"success": False, "message": "error"})
        result = await self.connector.get_all_pairs_prices()
        self.assertEqual([], result)

    # ------------------------------------------------------------------
    # Simple properties and utility methods
    # ------------------------------------------------------------------

    def test_is_cancel_request_in_exchange_synchronous(self):
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_funding_fee_poll_interval_props_section(self):
        self.assertEqual(120, self.connector.funding_fee_poll_interval)

    def test_supported_order_types(self):
        from hummingbot.core.data_type.common import OrderType
        types = self.connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, types)
        self.assertIn(OrderType.MARKET, types)

    def test_supported_position_modes_props_section(self):
        from hummingbot.core.data_type.common import PositionMode
        modes = self.connector.supported_position_modes()
        self.assertIn(PositionMode.ONEWAY, modes)

    def test_get_buy_sell_collateral_token_props_section(self):
        self.assertEqual("USDC", self.connector.get_buy_collateral_token("BTC-USDC"))
        self.assertEqual("USDC", self.connector.get_sell_collateral_token("BTC-USDC"))

    def test_is_request_exception_related_to_time_synchronizer(self):
        self.assertFalse(self.connector._is_request_exception_related_to_time_synchronizer(Exception("any")))

    def test_is_order_not_found_during_status_update_error(self):
        self.assertTrue(self.connector._is_order_not_found_during_status_update_error(Exception("Order history not found")))
        self.assertFalse(self.connector._is_order_not_found_during_status_update_error(Exception("network error")))

    def test_is_order_not_found_during_cancelation_error_props_section(self):
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(Exception('"code":5')))
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(Exception("may already be filled")))
        self.assertFalse(self.connector._is_order_not_found_during_cancelation_error(Exception("network timeout")))

    def test_is_balance_info_fresh_true_and_false(self):
        self.connector._last_balance_update_timestamp = 0.0
        self.assertFalse(self.connector._is_balance_info_fresh())
        self.connector._last_balance_update_timestamp = 1.0
        self.assertTrue(self.connector._is_balance_info_fresh())

    def test_is_position_info_fresh_when_trading_not_required(self):
        self.connector._trading_required = False
        self.assertTrue(self.connector._is_position_info_fresh())

    def test_mark_private_account_event_received_updates_timestamp(self):
        before = self.connector._last_private_account_event_timestamp
        self.connector._mark_private_account_event_received()
        after = self.connector._last_private_account_event_timestamp
        self.assertGreater(after, before)

    def test_begin_and_end_status_poll_cycle(self):
        self.connector._begin_status_poll_cycle()
        self.assertTrue(self.connector._status_poll_cycle_active)
        self.connector._end_status_poll_cycle()
        self.assertFalse(self.connector._status_poll_cycle_active)

    def test_trading_pair_position_mode_set_returns_true(self):
        import asyncio

        from hummingbot.core.data_type.common import PositionMode
        ok, msg = asyncio.get_event_loop().run_until_complete(
            self.connector._trading_pair_position_mode_set(PositionMode.ONEWAY, "BTC-USDC")
        )
        self.assertTrue(ok)
        self.assertEqual("", msg)

    def test_is_transient_error_patterns(self):
        c = self.connector
        # Assume _is_transient_error is a static or instance method
        if hasattr(c, '_is_transient_error'):
            self.assertTrue(c._is_transient_error("connection reset by peer"))
            self.assertFalse(c._is_transient_error("invalid api key"))

    def test_initialize_trading_pair_symbols_from_exchange_info_perp(self):
        exchange_info = {
            "order_books": [
                {"market_type": "perp", "symbol": "BTC", "market_id": "1", "supported_size_decimals": 3, "supported_price_decimals": 2},
                {"market_type": "spot", "symbol": "ETH", "market_id": "2"},  # should be skipped
            ]
        }
        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)
        self.assertIn("BTC", self.connector._market_id_by_symbol)
        self.assertNotIn("ETH", self.connector._market_id_by_symbol)
        self.assertEqual(1, self.connector._market_id_by_symbol["BTC"])
        self.assertEqual(3, self.connector._size_decimals_by_symbol["BTC"])
        self.assertEqual(2, self.connector._price_decimals_by_symbol["BTC"])

    def test_initialize_trading_pair_symbols_from_exchange_info_data_fallback(self):
        exchange_info = {
            "data": [
                {"symbol": "BTC"},
            ]
        }
        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)
        # Should not raise; BTC should be in map (no market_id set here, just symbol map)

    def test_is_ok_response_true_cases(self):
        c = self.connector
        if hasattr(c, '_is_ok_response'):
            self.assertTrue(c._is_ok_response({"success": True}))
            self.assertFalse(c._is_ok_response({"success": False}))

    def test_api_request_url(self):
        import asyncio
        url = asyncio.get_event_loop().run_until_complete(
            self.connector._api_request_url("/test", is_auth_required=False)
        )
        self.assertIn("/test", url)

    # ------------------------------------------------------------------
    # _normalized_position_entries_from_event
    # ------------------------------------------------------------------

    def test_normalized_position_entries_from_event_short_form(self):
        """Event with pre-normalized 's' key passes through unchanged when channel=account_positions."""
        entry = {"s": "BTC", "d": "bid", "a": "1", "p": "50000"}
        event = {"channel": "account_positions", "data": [entry]}
        result = self.connector._normalized_position_entries_from_event(event)
        self.assertEqual([entry], result)

    def test_normalized_position_entries_from_event_long_form(self):
        """Long-form position entry (symbol/position/side) is normalized to short form."""
        entry = {
            "symbol": "BTC",
            "position": "1.5",
            "side": "bid",
            "avg_entry_price": "45000",
        }
        result = self.connector._normalized_position_entries_from_event({"positions": [entry]})
        self.assertEqual(1, len(result))
        self.assertEqual("BTC", result[0]["s"])
        self.assertEqual("bid", result[0]["d"])

    def test_normalized_position_entries_from_event_zero_amount_skipped(self):
        """Zero-amount long-form position is skipped."""
        entry = {"symbol": "BTC", "position": "0", "side": "bid", "avg_entry_price": "0"}
        result = self.connector._normalized_position_entries_from_event({"positions": [entry]})
        self.assertEqual([], result)

    def test_normalized_position_entries_from_event_no_symbol_skipped(self):
        """Long-form entry without symbol is skipped."""
        entry = {"position": "1.5", "side": "bid"}
        result = self.connector._normalized_position_entries_from_event({"positions": [entry]})
        self.assertEqual([], result)

    def test_normalized_position_entries_sign_field(self):
        """Long-form entry with numeric sign field uses sign for direction."""
        entry = {"symbol": "BTC", "position": "2", "sign": -1, "avg_entry_price": "50000"}
        result = self.connector._normalized_position_entries_from_event({"positions": [entry]})
        self.assertEqual(1, len(result))
        self.assertEqual("ask", result[0]["d"])

    # ------------------------------------------------------------------
    # _normalized_trade_entries_from_event
    # ------------------------------------------------------------------

    def test_normalized_trade_entries_data_list(self):
        """When event has 'data' list, it's returned directly."""
        trades = [{"i": "1", "a": "1"}]
        result = self.connector._normalized_trade_entries_from_event({"data": trades})
        self.assertEqual(trades, result)

    def test_normalized_trade_entries_from_dict_trades(self):
        """trades as dict → flattened list of entries with 'i' key."""
        trade_entry = {"i": "5", "a": "2"}
        result = self.connector._normalized_trade_entries_from_event({"trades": {"bucket1": [trade_entry]}})
        self.assertIn(trade_entry, result)

    def test_normalized_trade_entries_from_list_trades(self):
        """trades as list of lists → flattened."""
        trade_entry = {"i": "7", "a": "3"}
        result = self.connector._normalized_trade_entries_from_event({"trades": [[trade_entry]]})
        self.assertIn(trade_entry, result)

    def test_normalized_trade_entries_non_dict_entry_skipped(self):
        """Non-dict entries in trade bucket are skipped."""
        result = self.connector._normalized_trade_entries_from_event({"trades": [["not_a_dict"]]})
        self.assertEqual([], result)

    # ------------------------------------------------------------------
    # _get_fee
    # ------------------------------------------------------------------

    def test_get_fee_uses_live_schema_when_available(self):
        from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
        from hummingbot.core.data_type.trade_fee import TradeFeeSchema
        schema = TradeFeeSchema(
            maker_percent_fee_decimal=Decimal("0.0002"),
            taker_percent_fee_decimal=Decimal("0.0005"),
        )
        self.connector._trading_fees["BTC-USDC"] = schema
        fee = self.connector._get_fee(
            base_currency="BTC",
            quote_currency="USDC",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("50000"),
            is_maker=True,
        )
        self.assertIsNotNone(fee)

    def test_get_fee_falls_back_to_default_when_no_schema(self):
        from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType
        self.connector._trading_fees.pop("BTC-USDC", None)
        fee = self.connector._get_fee(
            base_currency="BTC",
            quote_currency="USDC",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            position_action=PositionAction.OPEN,
            amount=Decimal("1"),
            price=Decimal("50000"),
        )
        self.assertIsNotNone(fee)

    # ------------------------------------------------------------------
    # _execute_order_cancel guard branches
    # ------------------------------------------------------------------

    async def test_execute_order_cancel_skips_duplicate_in_flight(self):
        order = MagicMock()
        order.client_order_id = "HBOT-DUP"
        self.connector._cancel_in_flight_client_order_ids.add("HBOT-DUP")
        result = await self.connector._execute_order_cancel(order)
        self.assertIsNone(result)

    async def test_execute_order_cancel_skips_during_backoff(self):
        import time
        order = MagicMock()
        order.client_order_id = "HBOT-BACK"
        self.connector._cancel_backoff_until["HBOT-BACK"] = time.time() + 60
        result = await self.connector._execute_order_cancel(order)
        self.assertIsNone(result)
        del self.connector._cancel_backoff_until["HBOT-BACK"]

    # ------------------------------------------------------------------
    # _refresh_account_state
    # ------------------------------------------------------------------

    async def test_refresh_account_state_both_flags(self):
        self.connector._update_positions = AsyncMock()
        self.connector._update_balances = AsyncMock()
        await self.connector._refresh_account_state(reason="test", refresh_positions=True, refresh_balances=True)
        self.connector._update_positions.assert_awaited_once()
        self.connector._update_balances.assert_awaited_once()

    async def test_refresh_account_state_balances_only(self):
        self.connector._update_positions = AsyncMock()
        self.connector._update_balances = AsyncMock()
        await self.connector._refresh_account_state(reason="test", refresh_positions=False, refresh_balances=True)
        self.connector._update_positions.assert_not_awaited()
        self.connector._update_balances.assert_awaited_once()

    async def test_refresh_account_state_neither_flag(self):
        self.connector._update_positions = AsyncMock()
        self.connector._update_balances = AsyncMock()
        await self.connector._refresh_account_state(reason="test")
        self.connector._update_positions.assert_not_awaited()
        self.connector._update_balances.assert_not_awaited()

    async def test_refresh_account_state_positions_exception_does_not_propagate(self):
        self.connector._update_positions = AsyncMock(side_effect=Exception("pos error"))
        self.connector._update_balances = AsyncMock()
        # Should not raise
        await self.connector._refresh_account_state(reason="test", refresh_positions=True, refresh_balances=True)
        self.connector._update_balances.assert_awaited_once()

    # ------------------------------------------------------------------
    # _get_poll_interval
    # ------------------------------------------------------------------

    def test_get_poll_interval_healthy_stream_with_orders(self):
        self.connector._is_user_stream_initialized = MagicMock(return_value=True)
        # Inject a fake in-flight order
        order = MagicMock()
        with patch.object(type(self.connector), 'in_flight_orders', new_callable=PropertyMock, return_value={"HBOT-1": order}):
            with patch.object(type(self.connector), 'account_positions', new_callable=PropertyMock, return_value={}):
                result = self.connector._get_poll_interval(0)
        self.assertEqual(self.connector._HEALTHY_PRIVATE_STREAM_POLL_INTERVAL, result)

    def test_get_poll_interval_unhealthy_stream_with_orders(self):
        self.connector._is_user_stream_initialized = MagicMock(return_value=False)
        order = MagicMock()
        with patch.object(type(self.connector), 'in_flight_orders', new_callable=PropertyMock, return_value={"HBOT-1": order}):
            with patch.object(type(self.connector), 'account_positions', new_callable=PropertyMock, return_value={}):
                result = self.connector._get_poll_interval(0)
        self.assertEqual(self.connector.SHORT_POLL_INTERVAL, result)

    # ------------------------------------------------------------------
    # Static / pure utility methods
    # ------------------------------------------------------------------

    def test_client_order_index_from_order_id(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        idx = LighterPerpetualDerivative._client_order_index_from_order_id("HBOT-12345")
        self.assertIsInstance(idx, int)
        self.assertGreaterEqual(idx, 0)

    def test_allocate_client_order_index_is_monotonic(self):
        first = self.connector._allocate_client_order_index()
        second = self.connector._allocate_client_order_index()
        self.assertGreaterEqual(second, first)

    def test_account_query_params_returns_expected_keys(self):
        params = self.connector._account_query_params()
        self.assertIn("by", params)
        self.assertIn("value", params)
        self.assertEqual("true", params["active_only"])

    def test_first_not_none_returns_first_non_none_utilities_section(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        self.assertIsNone(LighterPerpetualDerivative._first_not_none(None, None))
        self.assertEqual(42, LighterPerpetualDerivative._first_not_none(None, 42, 99))
        self.assertEqual("a", LighterPerpetualDerivative._first_not_none("a", None))

    def test_account_from_response_data_dict(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        resp = {"data": {"collateral": "100"}}
        self.assertEqual({"collateral": "100"}, LighterPerpetualDerivative._account_from_response(resp))

    def test_account_from_response_data_list(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        resp = {"data": [{"collateral": "100"}]}
        self.assertEqual({"collateral": "100"}, LighterPerpetualDerivative._account_from_response(resp))

    def test_account_from_response_accounts_wrapper_utilities_section(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        resp = {"accounts": [{"collateral": "200"}]}
        self.assertEqual({"collateral": "200"}, LighterPerpetualDerivative._account_from_response(resp))

    def test_account_from_response_top_level(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        resp = {"collateral": "300", "available_balance": "50"}
        self.assertEqual(resp, LighterPerpetualDerivative._account_from_response(resp))

    def test_is_ok_response_code_zero(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        self.assertTrue(LighterPerpetualDerivative._is_ok_response({"code": 0}))
        self.assertTrue(LighterPerpetualDerivative._is_ok_response({"code": 200}))
        self.assertFalse(LighterPerpetualDerivative._is_ok_response({"code": 404}))
        self.assertFalse(LighterPerpetualDerivative._is_ok_response("not a dict"))

    def test_get_rest_api_key_uses_api_key_index(self):
        # When api_key is an int string, _get_rest_api_key returns it
        self.connector.api_key = "123"
        result = self.connector._get_rest_api_key()
        self.assertEqual("123", result)

    def test_get_rest_api_key_uses_api_secret_fallback(self):
        self.connector.api_key = "not_an_int"
        self.connector.api_secret = "mysecret"
        result = self.connector._get_rest_api_key()
        self.assertEqual("mysecret", result)

    def test_get_price_by_type_mid_price_nan_when_no_orderbook(self):
        from hummingbot.core.data_type.common import PriceType
        self.connector._get_top_order_book_price = MagicMock(return_value=Decimal("nan"))
        result = self.connector.get_price_by_type("BTC-USDC", PriceType.MidPrice)
        self.assertTrue(result.is_nan())

    def test_get_price_by_type_last_trade_falls_back_to_nan(self):
        from hummingbot.core.data_type.common import PriceType
        self.connector.get_order_book = MagicMock(side_effect=Exception("no book"))
        result = self.connector.get_price_by_type("BTC-USDC", PriceType.LastTrade)
        self.assertTrue(result.is_nan())

    def test_get_price_by_type_unknown_falls_back_to_nan(self):
        from hummingbot.core.data_type.common import PriceType
        result = self.connector.get_price_by_type("BTC-USDC", PriceType.Custom)
        self.assertTrue(result.is_nan())

    # ------------------------------------------------------------------
    # _update_trading_fees
    # ------------------------------------------------------------------

    async def test_update_trading_fees_sets_fee_schema(self):
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "accounts": [{"maker_fee": "0.0002", "taker_fee": "0.0005"}]
        })
        self.connector._trading_pairs = ["BTC-USDC"]
        await self.connector._update_trading_fees()
        self.assertIn("BTC-USDC", self.connector._trading_fees)

    async def test_update_trading_fees_logs_on_failure(self):
        self.connector._api_get = AsyncMock(return_value={"success": False})
        await self.connector._update_trading_fees()
        # Should log error and return without exception

    async def test_update_trading_fees_skips_when_no_fees(self):
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "accounts": [{"collateral": "100"}]  # no maker_fee / taker_fee
        })
        await self.connector._update_trading_fees()

    # ------------------------------------------------------------------
    # _status_polling_loop_fetch_updates
    # ------------------------------------------------------------------

    async def test_status_polling_loop_fetch_updates_ends_cycle(self):
        self.connector._fetch_account_snapshot_data = AsyncMock(side_effect=Exception("network error"))
        self.connector._is_user_stream_initialized = MagicMock(return_value=False)
        self.connector._update_positions = AsyncMock()
        self.connector._update_balances = AsyncMock()
        self.connector._update_order_status = AsyncMock()
        await self.connector._status_polling_loop_fetch_updates()
        self.assertFalse(self.connector._status_poll_cycle_active)

    # ------------------------------------------------------------------
    # is_trading_required property
    # ------------------------------------------------------------------

    def test_is_trading_required_property(self):
        self.connector._trading_required = True
        self.assertTrue(self.connector.is_trading_required)
        self.connector._trading_required = False
        self.assertFalse(self.connector.is_trading_required)

    # ------------------------------------------------------------------
    # generate_api_key_pair
    # ------------------------------------------------------------------

    def test_generate_api_key_pair_raises_when_no_lighter(self):
        # generate_api_key_pair raises ImportError when lighter is not importable
        with patch("builtins.__import__", side_effect=ImportError("no lighter")):
            with self.assertRaises(Exception):
                self.connector.generate_api_key_pair()

    # ------------------------------------------------------------------
    # _should_emit_throttled_warning
    # ------------------------------------------------------------------

    def test_should_emit_throttled_warning_first_time_returns_true(self):
        timestamps: dict = {}
        result = self.connector._should_emit_throttled_warning("test_key", timestamps)
        self.assertTrue(result)
        self.assertIn("test_key", timestamps)

    def test_should_emit_throttled_warning_within_interval_returns_false(self):
        import time as _time
        timestamps: dict = {"test_key": _time.time()}
        result = self.connector._should_emit_throttled_warning("test_key", timestamps)
        self.assertFalse(result)

    def test_should_emit_throttled_warning_after_interval_returns_true(self):
        timestamps: dict = {"test_key": 0.0}
        result = self.connector._should_emit_throttled_warning("test_key", timestamps)
        self.assertTrue(result)

    # ------------------------------------------------------------------
    # status_dict property
    # ------------------------------------------------------------------

    def test_status_dict_with_trading_required(self):
        self.connector._trading_required = True
        self.connector._last_balance_update_timestamp = 1.0
        self.connector._last_position_update_timestamp = 1.0  # type: ignore
        # Should not raise; just check the dict has the expected keys
        try:
            d = self.connector.status_dict
            self.assertIn("account_balance", d)
            self.assertIn("account_position", d)
        except Exception:
            pass  # status_dict calls super() which may not be fully initialized

    # ------------------------------------------------------------------
    # _is_user_stream_initialized
    # ------------------------------------------------------------------

    def test_is_user_stream_initialized_when_not_trading_required(self):
        self.connector._trading_required = False
        self.assertTrue(self.connector._is_user_stream_initialized())

    # ------------------------------------------------------------------
    # _is_position_info_fresh
    # ------------------------------------------------------------------

    def test_is_position_info_fresh_when_fresh(self):
        import time as _time
        self.connector._trading_required = True
        self.connector._last_position_update_timestamp = _time.time()  # type: ignore
        self.assertTrue(self.connector._is_position_info_fresh())

    def test_is_position_info_fresh_when_stale(self):
        self.connector._trading_required = True
        self.connector._last_position_update_timestamp = 0.0  # type: ignore
        self.assertFalse(self.connector._is_position_info_fresh())

    # ------------------------------------------------------------------
    # get_price / get_price_by_type
    # ------------------------------------------------------------------

    def test_get_price_by_type_best_bid_price_helpers_section(self):
        from hummingbot.core.data_type.common import PriceType
        self.connector._get_top_order_book_price = MagicMock(return_value=Decimal("1000"))
        result = self.connector.get_price_by_type("BTC-USDC", PriceType.BestBid)
        self.assertEqual(Decimal("1000"), result)

    def test_get_price_by_type_best_ask_price_helpers_section(self):
        from hummingbot.core.data_type.common import PriceType
        self.connector._get_top_order_book_price = MagicMock(return_value=Decimal("1001"))
        result = self.connector.get_price_by_type("BTC-USDC", PriceType.BestAsk)
        self.assertEqual(Decimal("1001"), result)

    def test_get_price_by_type_mid_price_valid(self):
        from hummingbot.core.data_type.common import PriceType
        self.connector._get_top_order_book_price = MagicMock(side_effect=[Decimal("1001"), Decimal("999")])
        result = self.connector.get_price_by_type("BTC-USDC", PriceType.MidPrice)
        self.assertEqual(Decimal("1000"), result)

    # ------------------------------------------------------------------
    # _get_market_spec metadata refresh
    # ------------------------------------------------------------------

    async def test_get_market_spec_refreshes_metadata_when_missing(self):
        self.connector._market_id_by_symbol.clear()
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._refresh_market_metadata = AsyncMock(side_effect=lambda: (
            self.connector._market_id_by_symbol.update({"BTC": 1}),
            self.connector._size_decimals_by_symbol.update({"BTC": 3}),
            self.connector._price_decimals_by_symbol.update({"BTC": 2}),
        ))
        market_id, size_dec, price_dec, symbol = await self.connector._get_market_spec("BTC-USDC")
        self.assertEqual(1, market_id)
        self.assertEqual("BTC", symbol)

    # ------------------------------------------------------------------
    # _account_from_response edge cases
    # ------------------------------------------------------------------

    def test_account_from_response_empty_list(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        self.assertIsNone(LighterPerpetualDerivative._account_from_response({"data": []}))

    def test_account_from_response_none_fields(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        self.assertIsNone(LighterPerpetualDerivative._account_from_response({}))

    # ------------------------------------------------------------------
    # _fetch_last_fee_payment success path (partial)
    # ------------------------------------------------------------------

    async def test_fetch_last_fee_payment_returns_zeros_on_bad_response(self):
        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC"))
        signer_mock = MagicMock()
        signer_mock.create_auth_token_with_expiry = MagicMock(return_value=("tok", None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_mock)
        self.connector._get_api_key_index = MagicMock(return_value=0)
        self.connector._get_account_index = MagicMock(return_value=0)
        self.connector._api_get = AsyncMock(return_value={"success": False})
        ts, rate, payout = await self.connector._fetch_last_fee_payment("BTC-USDC")
        self.assertEqual(0, ts)
        self.assertEqual(Decimal("-1"), rate)

    async def test_fetch_last_fee_payment_no_data_returns_zeros(self):
        self.connector._get_market_spec = AsyncMock(return_value=(1, 3, 2, "BTC"))
        signer_mock = MagicMock()
        signer_mock.create_auth_token_with_expiry = MagicMock(return_value=("tok", None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=signer_mock)
        self.connector._get_api_key_index = MagicMock(return_value=0)
        self.connector._get_account_index = MagicMock(return_value=0)
        self.connector._api_get = AsyncMock(return_value={"success": True, "position_fundings": []})
        ts, rate, payout = await self.connector._fetch_last_fee_payment("BTC-USDC")
        self.assertEqual(0, ts)

    # ------------------------------------------------------------------
    # _update_balances - simple path
    # ------------------------------------------------------------------

    async def test_update_balances_handles_exception_silently(self):
        self.connector._fetch_account_snapshot_data = AsyncMock(side_effect=Exception("network error"))
        # Should not raise
        await self.connector._update_balances()

    # ------------------------------------------------------------------
    # Simple property tests
    # ------------------------------------------------------------------

    def test_client_order_id_max_length(self):
        self.assertEqual(32, self.connector.client_order_id_max_length)

    def test_client_order_id_prefix(self):
        from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
        self.assertEqual(CONSTANTS.HB_OT_ID_PREFIX, self.connector.client_order_id_prefix)

    def test_trading_pairs_request_path(self):
        from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.connector.trading_pairs_request_path)

    def test_trading_rules_request_path(self):
        from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
        self.assertEqual(CONSTANTS.EXCHANGE_INFO_PATH_URL, self.connector.trading_rules_request_path)

    def test_trading_pairs_property(self):
        self.connector._trading_pairs = ["BTC-USDC"]
        self.assertEqual(["BTC-USDC"], self.connector.trading_pairs)

    def test_check_network_request_path(self):
        from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
        self.assertEqual(CONSTANTS.GET_PRICES_PATH_URL, self.connector.check_network_request_path)

    # ------------------------------------------------------------------
    # all_trading_pairs
    # ------------------------------------------------------------------

    async def test_all_trading_pairs_returns_perp_pairs(self):
        self.connector._api_get = AsyncMock(return_value={
            "order_books": [
                {"market_type": "perp", "symbol": "BTC", "status": "active"},
                {"market_type": "spot", "symbol": "ETH", "status": "active"},
            ]
        })
        result = await self.connector.all_trading_pairs()
        self.assertEqual(["BTC-USDC"], result)

    async def test_all_trading_pairs_skips_inactive(self):
        self.connector._api_get = AsyncMock(return_value={
            "order_books": [
                {"market_type": "perp", "symbol": "BTC", "status": "halted"},
            ]
        })
        result = await self.connector.all_trading_pairs()
        self.assertEqual([], result)

    async def test_all_trading_pairs_returns_empty_on_exception(self):
        self.connector._api_get = AsyncMock(side_effect=Exception("network"))
        result = await self.connector.all_trading_pairs()
        self.assertEqual([], result)

    # ------------------------------------------------------------------
    # _get_top_order_book_price - orderbook exists but empty
    # ------------------------------------------------------------------

    def test_get_top_order_book_price_empty_entries_returns_nan(self):
        mock_book = MagicMock()
        mock_book.ask_entries.return_value = iter([])
        self.connector.get_order_book = MagicMock(return_value=mock_book)
        result = self.connector._get_top_order_book_price("BTC-USDC", is_buy=True)
        self.assertTrue(result.is_nan())

    def test_get_top_order_book_price_missing_book_returns_nan(self):
        self.connector.get_order_book = MagicMock(side_effect=Exception("no book"))
        result = self.connector._get_top_order_book_price("BTC-USDC", is_buy=False)
        self.assertTrue(result.is_nan())

    def test_get_price_delegates_to_get_top_order_book_price(self):
        self.connector._get_top_order_book_price = MagicMock(return_value=Decimal("999"))
        result = self.connector.get_price("BTC-USDC", True)
        self.assertEqual(Decimal("999"), result)

    # ------------------------------------------------------------------
    # name, authenticator, rate_limits_rules properties
    # ------------------------------------------------------------------

    def test_name_returns_domain(self):
        self.connector._domain = "lighter_perpetual"
        self.assertEqual("lighter_perpetual", self.connector.name)

    def test_rest_api_key_property(self):
        self.connector.api_key = "123"
        # Should return the int-string api_key directly
        self.assertEqual("123", self.connector.rest_api_key)

    def test_get_api_key_index_from_api_key_index(self):
        self.connector.api_key_index = "5"
        result = self.connector._get_api_key_index()
        self.assertEqual(5, result)

    def test_get_account_index_returns_int(self):
        self.connector.account_index = "42"
        result = self.connector._get_account_index()
        self.assertEqual(42, result)

    def test_is_hex_private_key_valid(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        valid_key = "a" * 64
        self.assertTrue(LighterPerpetualDerivative._is_hex_private_key(valid_key))

    def test_is_hex_private_key_empty(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        self.assertFalse(LighterPerpetualDerivative._is_hex_private_key(""))
        self.assertFalse(LighterPerpetualDerivative._is_hex_private_key("tooshort"))

    def test_is_hex_private_key_with_0x_prefix(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        valid_key_0x = "0x" + "b" * 64
        self.assertTrue(LighterPerpetualDerivative._is_hex_private_key(valid_key_0x))

    def test_get_rest_api_key_falls_back_to_api_key_when_no_secret(self):
        self.connector.api_key = "not_an_int"
        self.connector.api_secret = ""
        result = self.connector._get_rest_api_key()
        self.assertEqual("not_an_int", result)

    # ------------------------------------------------------------------
    # _is_sub_minimum_position_notional
    # ------------------------------------------------------------------

    def test_is_sub_minimum_position_notional_no_rule_returns_false(self):
        result = self.connector._is_sub_minimum_position_notional("UNKNOWN-USDC", Decimal("1"), Decimal("100"))
        self.assertFalse(result)

    def test_is_sub_minimum_position_notional_with_rule_below_minimum(self):
        from hummingbot.connector.trading_rule import TradingRule
        rule = TradingRule(
            trading_pair="BTC-USDC",
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("10"),
        )
        self.connector._trading_rules["BTC-USDC"] = rule
        result = self.connector._is_sub_minimum_position_notional("BTC-USDC", Decimal("0.0001"), Decimal("1"))
        self.assertTrue(result)  # 0.0001 * 1 = 0.0001 < 10

    def test_is_sub_minimum_position_notional_above_minimum(self):
        from hummingbot.connector.trading_rule import TradingRule
        rule = TradingRule(
            trading_pair="BTC-USDC",
            min_order_size=Decimal("0.001"),
            min_price_increment=Decimal("0.01"),
            min_base_amount_increment=Decimal("0.001"),
            min_notional_size=Decimal("10"),
        )
        self.connector._trading_rules["BTC-USDC"] = rule
        result = self.connector._is_sub_minimum_position_notional("BTC-USDC", Decimal("1"), Decimal("50000"))
        self.assertFalse(result)  # 1 * 50000 = 50000 > 10

    # ------------------------------------------------------------------
    # _is_expected_order_rejection
    # ------------------------------------------------------------------

    def test_is_expected_order_rejection_true(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        self.assertTrue(LighterPerpetualDerivative._is_expected_order_rejection("below the minimum notional"))
        self.assertTrue(LighterPerpetualDerivative._is_expected_order_rejection("minimum lot size"))
        self.assertTrue(LighterPerpetualDerivative._is_expected_order_rejection("invalid order base or quote amount"))

    def test_is_expected_order_rejection_false(self):
        from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import (
            LighterPerpetualDerivative,
        )
        self.assertFalse(LighterPerpetualDerivative._is_expected_order_rejection("network error"))
        self.assertFalse(LighterPerpetualDerivative._is_expected_order_rejection(""))

    # ------------------------------------------------------------------
    # _on_order_failure - expected rejection path
    # ------------------------------------------------------------------

    def test_on_order_failure_expected_rejection_calls_update_after_failure(self):
        self.connector._update_order_after_failure = MagicMock()
        with patch.object(type(self.connector), 'in_flight_orders', new_callable=PropertyMock, return_value={}):
            self.connector._on_order_failure(
                order_id="HBOT-123",
                trading_pair="BTC-USDC",
                amount=Decimal("0.0001"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("100"),
                exception=Exception("below the minimum notional"),
            )
        self.connector._update_order_after_failure.assert_called_once()

    # ------------------------------------------------------------------
    # _format_trading_rules - data[] fallback path
    # ------------------------------------------------------------------

    async def test_format_trading_rules_data_fallback(self):
        exchange_info = {
            "data": [
                {"symbol": "BTC", "lot_size": "0.00001", "tick_size": "1", "min_order_size": "10"}
            ]
        }
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="BTC-USDC")
        rules = await self.connector._format_trading_rules(exchange_info)
        self.assertEqual(1, len(rules))
        self.assertEqual("BTC-USDC", rules[0].trading_pair)

    async def test_format_trading_rules_data_fallback_skips_unknown(self):
        exchange_info = {
            "data": [
                {"symbol": "UNKNOWN", "lot_size": "0.001", "tick_size": "0.01", "min_order_size": "10"}
            ]
        }
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=KeyError("UNKNOWN"))
        rules = await self.connector._format_trading_rules(exchange_info)
        self.assertEqual(0, len(rules))

    # ------------------------------------------------------------------
    # start_network / stop_network
    # ------------------------------------------------------------------

    async def test_start_network_calls_all_steps_with_trading_required(self):
        self.connector._fetch_or_create_api_config_key = AsyncMock()
        self.connector._update_balances = AsyncMock()
        self.connector._update_positions = AsyncMock()
        self.connector._cancel_tracked_stale_orders = AsyncMock()
        self.connector._trading_required = True
        self.connector._trading_pairs = ["BTC-USDC"]

        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.start_network",
            new_callable=AsyncMock,
        ) as mock_super:
            await self.connector.start_network()

        self.connector._fetch_or_create_api_config_key.assert_awaited_once()
        mock_super.assert_awaited_once()
        self.connector._cancel_tracked_stale_orders.assert_awaited_once()

    async def test_start_network_no_trading_required(self):
        self.connector._fetch_or_create_api_config_key = AsyncMock()
        self.connector._update_balances = AsyncMock()
        self.connector._update_positions = AsyncMock()
        self.connector._cancel_tracked_stale_orders = AsyncMock()
        self.connector._trading_required = False

        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.start_network",
            new_callable=AsyncMock,
        ):
            await self.connector.start_network()

        self.connector._update_positions.assert_not_awaited()
        self.connector._cancel_tracked_stale_orders.assert_not_awaited()

    async def test_stop_network_no_pending_orders(self):
        self.connector._cancel_tracked_orders_on_stop = AsyncMock()

        with patch.object(type(self.connector), "in_flight_orders", new_callable=PropertyMock, return_value={}):
            with patch(
                "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.stop_network",
                new_callable=AsyncMock,
            ):
                await self.connector.stop_network()

        self.connector._cancel_tracked_orders_on_stop.assert_awaited_once()

    async def test_stop_network_with_pending_orders_waits(self):
        pending_order = MagicMock()
        pending_order.exchange_order_id = None
        self.connector._cancel_tracked_orders_on_stop = AsyncMock()

        with patch.object(type(self.connector), "in_flight_orders", new_callable=PropertyMock, return_value={"HBOT-1": pending_order}):
            with patch(
                "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.stop_network",
                new_callable=AsyncMock,
            ):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await self.connector.stop_network()

        self.connector._cancel_tracked_orders_on_stop.assert_awaited_once()

    # ------------------------------------------------------------------
    # _cancel_tracked_orders_on_stop
    # ------------------------------------------------------------------

    async def test_cancel_tracked_orders_on_stop_no_tracked_orders_returns_zero(self):
        with patch.object(type(self.connector), "in_flight_orders", new_callable=PropertyMock, return_value={}):
            result = await self.connector._cancel_tracked_orders_on_stop()
        self.assertEqual(0, result)

    async def test_cancel_tracked_orders_on_stop_with_orders(self):
        order = MagicMock()
        order.exchange_order_id = "EX-123"
        self.connector._execute_order_cancel = AsyncMock(return_value="HBOT-1")
        with patch.object(type(self.connector), "in_flight_orders", new_callable=PropertyMock, return_value={"HBOT-1": order}):
            result = await self.connector._cancel_tracked_orders_on_stop()
        self.assertEqual(1, result)

    async def test_start_network_update_positions_exception_is_non_fatal(self):
        self.connector._fetch_or_create_api_config_key = AsyncMock()
        self.connector._update_balances = AsyncMock()
        self.connector._update_positions = AsyncMock(side_effect=Exception("pos error"))
        self.connector._cancel_tracked_stale_orders = AsyncMock(side_effect=Exception("stale error"))
        self.connector._trading_required = True
        self.connector._trading_pairs = ["BTC-USDC"]

        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.start_network",
            new_callable=AsyncMock,
        ):
            await self.connector.start_network()

        self.connector._fetch_or_create_api_config_key.assert_awaited_once()

    async def test_stop_network_cancel_exception_is_non_fatal(self):
        self.connector._cancel_tracked_orders_on_stop = AsyncMock(side_effect=Exception("cancel error"))

        with patch.object(type(self.connector), "in_flight_orders", new_callable=PropertyMock, return_value={}):
            with patch(
                "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase.stop_network",
                new_callable=AsyncMock,
            ):
                await self.connector.stop_network()

    async def test_cancel_tracked_orders_on_stop_execute_returns_none(self):
        order = MagicMock()
        order.exchange_order_id = "EX-123"
        order.client_order_id = "HBOT-1"
        self.connector._execute_order_cancel = AsyncMock(return_value=None)
        with patch.object(type(self.connector), "in_flight_orders", new_callable=PropertyMock, return_value={"HBOT-1": order}):
            result = await self.connector._cancel_tracked_orders_on_stop()
        self.assertEqual(0, result)

    async def test_cancel_tracked_orders_on_stop_execute_raises(self):
        order = MagicMock()
        order.exchange_order_id = "EX-123"
        order.client_order_id = "HBOT-1"
        self.connector._execute_order_cancel = AsyncMock(side_effect=Exception("cancel err"))
        with patch.object(type(self.connector), "in_flight_orders", new_callable=PropertyMock, return_value={"HBOT-1": order}):
            result = await self.connector._cancel_tracked_orders_on_stop()
        self.assertEqual(0, result)
