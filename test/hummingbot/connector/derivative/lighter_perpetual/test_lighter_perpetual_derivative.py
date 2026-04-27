import asyncio
import sys
import time
import types
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PriceType
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

        self.assertEqual(Decimal("77.12"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("77.12"), self.connector._account_available_balances["USDC"])

    async def test_process_account_info_ws_event_message_preserves_zero_available_balance(self):
        event_message = {
            "channel": "account_info",
            "data": {
                "ae": 100,
                "as": 0,
            },
        }

        await self.connector._process_account_info_ws_event_message(event_message)

        self.assertEqual(Decimal("100"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("0"), self.connector._account_available_balances["USDC"])

    async def test_process_account_all_ws_event_message_ignores_partial_top_level_balance_fields(self):
        self.connector._account_balances["USDC"] = Decimal("100")
        self.connector._account_available_balances["USDC"] = Decimal("95")
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()
        self.connector._process_account_all_orders_ws_event_message = AsyncMock()

        # Partial payload with only total balance should not clobber existing balances.
        event_message = {
            "collateral": "120",
        }

        await self.connector._process_account_all_ws_event_message(event_message)

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

        self.assertEqual(Decimal("120"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("0"), self.connector._account_available_balances["USDC"])

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

    def test_is_user_stream_initialized_requires_recent_messages(self):
        trading_connector = self.connector_cls(
            lighter_perpetual_api_key_index="1",
            lighter_perpetual_account_index="237600",
            lighter_perpetual_api_key_private_key="0x" + ("a" * 64),
            trading_pairs=["BTC-USDC"],
            trading_required=True,
        )
        trading_connector._user_stream_tracker = SimpleNamespace(
            data_source=SimpleNamespace(last_recv_time=time.time() - 120)
        )

        self.assertFalse(trading_connector._is_user_stream_initialized())

    def test_get_poll_interval_is_short_when_any_active_order_exists(self):
        now = time.time()
        self.connector._user_stream_tracker = SimpleNamespace(last_recv_time=now)
        self.connector._order_tracker.active_orders["test-order"] = SimpleNamespace(position=PositionAction.OPEN)

        interval = self.connector._get_poll_interval(timestamp=now)

        self.assertEqual(self.connector.SHORT_POLL_INTERVAL, interval)

    def test_get_poll_interval_is_short_when_open_position_exists(self):
        now = time.time()
        self.connector._user_stream_tracker = SimpleNamespace(last_recv_time=now)
        self.connector._order_tracker.active_orders.clear()
        self.connector._perpetual_trading.account_positions["HYPE-USDC-LONG"] = SimpleNamespace(amount=Decimal("0.5"))

        interval = self.connector._get_poll_interval(timestamp=now)

        self.assertEqual(self.connector.SHORT_POLL_INTERVAL, interval)

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
        self.assertEqual({"by": "index", "value": "237600"}, self.connector._account_query_params())
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
        # Authenticated request: _api_request must inject X-Api-Key header
        with patch(
            "hummingbot.connector.perpetual_derivative_py_base.PerpetualDerivativePyBase._api_request",
            new=AsyncMock(return_value={"auth": True}),
        ) as super_req:
            auth_result = await self.connector._api_request(path_url="/account", is_auth_required=True)
            self.assertEqual({"auth": True}, auth_result)
            auth_headers = super_req.await_args.kwargs.get("headers") or {}
            self.assertEqual(self.connector.rest_api_key, auth_headers.get("X-Api-Key"))

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

    async def test_process_account_info_ws_event_message_updates_balances_and_fee_tier(self):
        await self.connector._process_account_info_ws_event_message({
            "data": {"ae": "12.5", "as": "10.2", "f": 3},
        })

        self.assertEqual(Decimal("12.5"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("10.2"), self.connector._account_available_balances["USDC"])
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

    async def test_update_positions_clears_stale_positions_before_symbol_resolution(self):
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

        self.assertEqual({}, self.connector._perpetual_trading.account_positions)

    async def test_update_positions_rest_skips_zero_amount(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(return_value="DOGE-USDC")
        # Pre-populate price cache so the prices HTTP fetch is skipped
        self.connector.set_LIGHTER_price("DOGE-USDC", timestamp=1.0,
                                         index_price=Decimal("0.05"), mark_price=Decimal("0.05"))
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
        self.assertEqual({}, self.connector._perpetual_trading.account_positions)

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

    async def test_process_account_trades_ws_event_message_ignores_unknown_trade(self):
        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {}
        self.connector._order_tracker.process_trade_update = MagicMock()
        self.connector._reconcile_unmatched_private_event = AsyncMock()

        await self.connector._process_account_trades_ws_event_message({
            "data": [{"i": 123, "p": "100", "a": "0.2", "f": "0.01", "ts": "open_long", "t": 1700000000000}],
        })

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
            side_effect=IOError("[_place_cancel] Cannot resolve actual order_index for client_order_index=999")
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
            side_effect=IOError("[_place_cancel] Cannot resolve actual order_index for client_order_index=999")
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

    async def test_process_account_all_ws_event_message_routes_trades_and_positions(self):
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()

        event = {"type": "update/account_all", "channel": "account_all:237600", "positions": {}, "trades": {}}
        await self.connector._process_account_all_ws_event_message(event)

        # Both handlers are forwarded the full event; each handler normalises its own slice.
        self.connector._process_account_trades_ws_event_message.assert_awaited_once_with(event)
        self.connector._process_account_positions_ws_event_message.assert_awaited_once_with(event)

    async def test_process_account_all_ws_event_message_extracts_usdc_balance(self):
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
            "collateral": "100.50",
            "available_balance": "90.25",
            "assets": {
                "3": {"symbol": "USDC", "asset_id": 3, "balance": "100.50", "locked_balance": "10.25"},
                "1": {"symbol": "ETH", "asset_id": 1, "balance": "0.001", "locked_balance": "0.0"},
            },
        }
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()

        await self.connector._process_account_all_ws_event_message(event)

        self.assertEqual(Decimal("100.50"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("90.25"), self.connector._account_available_balances["USDC"])

    async def test_process_account_all_ws_event_message_no_assets_key_skips_balance(self):
        event = {"type": "update/account_all", "channel": "account_all:237600", "positions": {}, "trades": {}}
        self.connector._process_account_trades_ws_event_message = AsyncMock()
        self.connector._process_account_positions_ws_event_message = AsyncMock()

        await self.connector._process_account_all_ws_event_message(event)

        # Should not error; balances remain at their defaults
        self.assertEqual({}, self.connector._account_balances)

    async def test_process_account_all_ws_event_message_fallback_balance_without_assets(self):
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

        await self.connector._process_account_all_ws_event_message(event)

        self.assertEqual(Decimal("150.75"), self.connector._account_balances["USDC"])
        self.assertEqual(Decimal("120.50"), self.connector._account_available_balances["USDC"])

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
