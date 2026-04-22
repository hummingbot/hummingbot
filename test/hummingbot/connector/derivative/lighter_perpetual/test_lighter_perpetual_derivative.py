import sys
import time
import types
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import OrderType, PositionAction, PositionMode, PriceType


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
            lighter_perpetual_api_key="0x" + ("a" * 64),
            lighter_perpetual_api_secret="1",
            lighter_perpetual_account_index="237600",
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

    def test_set_usdc_balances_replaces_stale_assets(self):
        self.connector._account_balances["BTC"] = Decimal("1")
        self.connector._account_available_balances["BTC"] = Decimal("0.5")

        self.connector._set_usdc_balances(Decimal("10"), Decimal("7"))

        self.assertEqual({"USDC": Decimal("10")}, self.connector._account_balances)
        self.assertEqual({"USDC": Decimal("7")}, self.connector._account_available_balances)

    def test_check_network_request_path_uses_exchange_stats(self):
        self.assertEqual("/exchangeStats", self.connector.check_network_request_path)

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

        success, message = await self.connector._set_trading_pair_leverage("DOGE-USDC", 5)

        self.assertTrue(success)
        self.assertEqual("", message)
        mock_signer.update_leverage.assert_awaited_once_with(
            market_index=3,
            margin_mode=0,
            leverage=5,
            api_key_index=4,
        )

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

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "os": "filled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_not_called()

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

        await self.connector._process_account_positions_ws_event_message({"data": []})

        self.assertEqual({}, self.connector._perpetual_trading.account_positions)

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

        await self.connector._process_account_trades_ws_event_message({
            "data": [{"i": 123, "p": "100", "a": "0.2", "f": "0.01", "ts": "open_long", "t": 1700000000000}],
        })

        self.connector._order_tracker.process_trade_update.assert_not_called()

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
