import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from hummingbot.core.data_type.common import PositionAction, TradeType


def _ensure_limit_order_stub():
    module_name = "hummingbot.core.data_type.limit_order"
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class LimitOrder:
        pass

    stub_module.LimitOrder = LimitOrder
    sys.modules[module_name] = stub_module


def _ensure_order_book_stub():
    module_name = "hummingbot.core.data_type.order_book"
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
            lighter_perpetual_api_key="1",
            lighter_perpetual_api_secret="0xabc",
            lighter_perpetual_account_index="237600",
            trading_pairs=["BTC-USDC"],
            trading_required=False,
        )

    async def test_update_balances_parses_collateral(self):
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {
                "collateral": "123.45",
                "availableCollateral": "120.11",
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

    def test_get_api_key_index_prefers_numeric_api_key(self):
        self.connector.api_key = "12"
        self.assertEqual(12, self.connector._get_api_key_index())

    def test_get_api_key_index_uses_numeric_api_secret_fallback(self):
        self.connector.api_key = "not-a-number"
        self.connector.api_secret = "34"
        self.connector.api_key_index = ""

        self.assertEqual(34, self.connector._get_api_key_index())

    def test_get_api_key_index_raises_for_non_numeric_config(self):
        self.connector.api_key = "not-a-number"
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

    async def test_fetch_or_create_api_config_key_skips_when_index_already_configured(self):
        self.connector.api_config_key = "configured"
        self.connector.api_key_index = "4"
        self.connector._api_get = AsyncMock()

        await self.connector._fetch_or_create_api_config_key()

        self.connector._api_get.assert_not_called()

    async def test_fetch_or_create_api_config_key_warns_when_key_not_found(self):
        mock_logger = MagicMock()
        self.connector.api_key = "my_public_key"
        self.connector.api_secret = ""
        self.connector.api_config_key = "my_public_key"
        self.connector.api_key_index = ""
        self.connector.account_index = "237600"
        self.connector._api_get = AsyncMock(return_value={
            "api_keys": [{"api_key_index": 1, "public_key": "other_key"}]
        })

        with patch.object(self.connector, "logger", return_value=mock_logger):
            await self.connector._fetch_or_create_api_config_key()

        self.assertEqual("", self.connector.api_key_index)
        mock_logger.warning.assert_called_once()

    async def test_fetch_or_create_api_config_key_skips_when_credentials_missing(self):
        mock_logger = MagicMock()
        self.connector.account_index = ""
        self.connector.api_key = ""
        self.connector.api_secret = ""
        self.connector.api_config_key = ""
        self.connector._api_get = AsyncMock()

        with patch.object(self.connector, "logger", return_value=mock_logger):
            await self.connector._fetch_or_create_api_config_key()

        self.connector._api_get.assert_not_called()
        mock_logger.warning.assert_called_once()

    def test_get_signer_private_key_prefers_explicit_private_key(self):
        self.connector.private_key = "0xsigner"
        self.connector.api_key = "public"
        self.connector.api_secret = "secret"

        self.assertEqual("0xsigner", self.connector._get_signer_private_key())

    def test_get_signer_private_key_uses_non_numeric_api_key(self):
        self.connector.private_key = ""
        self.connector.api_key = "0xapi_key_private"
        self.connector.api_secret = "123"

        self.assertEqual("0xapi_key_private", self.connector._get_signer_private_key())

    def test_get_signer_private_key_uses_non_numeric_api_secret(self):
        self.connector.private_key = ""
        self.connector.api_key = "123"
        self.connector.api_secret = "0xapi_secret_private"

        self.assertEqual("0xapi_secret_private", self.connector._get_signer_private_key())

    def test_get_signer_private_key_raises_when_not_available(self):
        self.connector.private_key = ""
        self.connector.api_key = "123"
        self.connector.api_secret = "456"

        with self.assertRaises(ValueError):
            self.connector._get_signer_private_key()

    def test_generate_api_key_pair_returns_private_and_public_keys(self):
        fake_lighter_module = types.SimpleNamespace(create_api_key=lambda: ("priv", "pub", None))
        with patch.dict(sys.modules, {"lighter": fake_lighter_module}):
            private_key, public_key = self.connector.generate_api_key_pair()

        self.assertEqual("priv", private_key)
        self.assertEqual("pub", public_key)

    def test_generate_api_key_pair_raises_when_sdk_returns_error(self):
        fake_lighter_module = types.SimpleNamespace(create_api_key=lambda: (None, None, "boom"))
        with patch.dict(sys.modules, {"lighter": fake_lighter_module}):
            with self.assertRaises(ValueError):
                self.connector.generate_api_key_pair()

    def test_authenticator_uses_rest_api_key_and_account_identifier(self):
        self.connector.api_key = "public"
        self.connector.api_secret = "secret"
        self.connector.account_index = "237600"

        auth = self.connector.authenticator

        self.assertEqual("secret", auth.api_key)
        self.assertEqual("secret", auth.api_secret)
        self.assertEqual("237600", auth.user_wallet_public_key)

    def test_rate_limits_rules_returns_default_limits_without_api_key(self):
        import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as C

        self.connector.api_key = ""

        limits = self.connector.rate_limits_rules

        self.assertEqual(C.RATE_LIMITS, limits)

    def test_rate_limits_rules_uses_fee_tier_when_api_key_present(self):
        import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as C

        self.connector.api_key = "configured-key"
        self.connector._fee_tier = 4

        limits = self.connector.rate_limits_rules

        self.assertEqual(C.LIGHTER_LIMIT_ID, limits[0].limit_id)
        self.assertEqual(C.FEE_TIER_LIMITS[4], limits[0].limit)

    def test_rate_limits_rules_uses_default_tier_2_limit_for_unknown_fee_tier(self):
        import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as C

        self.connector.api_key = "configured-key"
        self.connector._fee_tier = 999

        limits = self.connector.rate_limits_rules

        self.assertEqual(C.LIGHTER_TIER_2_LIMIT, limits[0].limit)

    def test_get_lighter_signer_client_is_cached(self):
        captured_kwargs = {}

        class MockSignerClient:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        fake_lighter_module = types.SimpleNamespace(
            signer_client=types.SimpleNamespace(SignerClient=MockSignerClient)
        )
        self.connector.api_key = "7"
        self.connector.api_secret = "0xabc"
        self.connector.account_index = "237600"
        self.connector._lighter_signer_client = None

        with patch.dict(sys.modules, {"lighter": fake_lighter_module}):
            client_first = self.connector._get_lighter_signer_client()
            client_second = self.connector._get_lighter_signer_client()

        self.assertIs(client_first, client_second)
        self.assertEqual(237600, captured_kwargs["account_index"])
        self.assertIn(7, captured_kwargs["api_private_keys"])

    def test_create_web_assistants_factory_returns_factory(self):
        factory = self.connector._create_web_assistants_factory()

        self.assertIsNotNone(factory)

    def test_create_order_book_data_source_uses_connector_and_domain(self):
        data_source = self.connector._create_order_book_data_source()

        self.assertEqual(self.connector, data_source._connector)
        self.assertEqual(self.connector.domain, data_source._domain)

    def test_create_user_stream_data_source_uses_connector_and_auth(self):
        data_source = self.connector._create_user_stream_data_source()

        self.assertEqual(self.connector, data_source._connector)
        self.assertEqual(self.connector.domain, data_source._domain)
        self.assertEqual(self.connector.account_index, data_source._auth.user_wallet_public_key)

    def test_get_rest_api_key_returns_non_numeric_api_key_when_secret_missing(self):
        self.connector.api_key = "public-key"
        self.connector.api_secret = ""

        self.assertEqual("public-key", self.connector._get_rest_api_key())

    def test_set_lighter_price_keeps_latest_timestamp(self):
        self.connector.set_LIGHTER_price("BTC-USDC", 200.0, Decimal("101"), Decimal("102"))
        self.connector.set_LIGHTER_price("BTC-USDC", 199.0, Decimal("99"), Decimal("100"))

        price_record = self.connector.get_LIGHTER_price("BTC-USDC")
        self.assertEqual(200.0, price_record.timestamp)
        self.assertEqual(Decimal("101"), price_record.index_price)
        self.assertEqual(Decimal("102"), price_record.mark_price)

    async def test_api_request_adds_x_api_key_header(self):
        from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase

        self.connector.api_key = "123"
        with patch.object(
            PerpetualDerivativePyBase,
            "_api_request",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as super_api_request:
            response = await self.connector._api_request(path_url="/test", headers={"Existing": "value"})

        self.assertEqual({"ok": True}, response)
        called_headers = super_api_request.call_args.kwargs["headers"]
        self.assertEqual("123", called_headers["X-Api-Key"])
        self.assertEqual("value", called_headers["Existing"])

    async def test_api_request_without_rest_api_key_leaves_headers_unchanged(self):
        from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase

        self.connector.api_key = ""
        self.connector.api_secret = ""
        with patch.object(
            PerpetualDerivativePyBase,
            "_api_request",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as super_api_request:
            await self.connector._api_request(path_url="/test", headers={"Existing": "value"})

        called_headers = super_api_request.call_args.kwargs["headers"]
        self.assertEqual({"Existing": "value"}, called_headers)

    async def test_api_request_without_headers_passes_api_key_header(self):
        from hummingbot.connector.perpetual_derivative_py_base import PerpetualDerivativePyBase

        self.connector.api_key = "55"
        with patch.object(
            PerpetualDerivativePyBase,
            "_api_request",
            new_callable=AsyncMock,
            return_value={"ok": True},
        ) as super_api_request:
            await self.connector._api_request(path_url="/test", headers=None)

        called_headers = super_api_request.call_args.kwargs["headers"]
        self.assertEqual({"X-Api-Key": "55"}, called_headers)

    async def test_process_account_order_updates_ws_event_message_updates_tracked_order(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        self.connector._order_tracker.process_order_update = MagicMock()

        with patch.object(
            type(self.connector._order_tracker),
            "all_updatable_orders",
            new_callable=PropertyMock,
            return_value={"HBOT-1": tracked_order},
        ):
            await self.connector._process_account_order_updates_ws_event_message({
                "data": [{"i": 123, "os": "filled", "ut": 1700000000000}],
            })

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual("123", order_update.exchange_order_id)

    async def test_process_account_order_updates_ws_event_message_ignores_unknown_order(self):
        self.connector._order_tracker.process_order_update = MagicMock()

        with patch.object(
            type(self.connector._order_tracker),
            "all_updatable_orders",
            new_callable=PropertyMock,
            return_value={},
        ):
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

    async def test_process_account_trades_ws_event_message_processes_tracked_trade(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.quote_asset = "USDC"
        self.connector._order_tracker.process_trade_update = MagicMock()

        with patch.object(
            type(self.connector._order_tracker),
            "all_fillable_orders",
            new_callable=PropertyMock,
            return_value={"HBOT-1": tracked_order},
        ):
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
        self.connector._order_tracker.process_trade_update = MagicMock()

        with patch.object(
            type(self.connector._order_tracker),
            "all_fillable_orders",
            new_callable=PropertyMock,
            return_value={},
        ):
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
        self.connector._order_tracker.process_trade_update = MagicMock()

        with patch.object(
            type(self.connector._order_tracker),
            "all_fillable_orders",
            new_callable=PropertyMock,
            return_value={"HBOT-1": tracked_order},
        ):
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

        self.connector._process_account_trades_ws_event_message.assert_awaited_once_with(event)
        self.connector._process_account_positions_ws_event_message.assert_awaited_once_with(event)

    async def test_process_account_all_ws_event_message_extracts_usdc_balance(self):
        event = {
            "type": "update/account_all",
            "channel": "account_all:237600",
            "positions": {},
            "trades": {},
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

    # ---------------------------------------------------------------------------
    # Static / class-level utility method tests
    # ---------------------------------------------------------------------------

    def test_is_int_string_returns_true_for_numeric_strings(self):
        cls = self.connector_cls
        self.assertTrue(cls._is_int_string("0"))
        self.assertTrue(cls._is_int_string("123"))
        self.assertTrue(cls._is_int_string("-5"))

    def test_is_int_string_returns_false_for_non_numeric(self):
        cls = self.connector_cls
        self.assertFalse(cls._is_int_string("abc"))
        self.assertFalse(cls._is_int_string(""))
        self.assertFalse(cls._is_int_string(None))

    def test_is_ok_response_true_for_success_flag(self):
        cls = self.connector_cls
        self.assertTrue(cls._is_ok_response({"success": True}))
        self.assertFalse(cls._is_ok_response({"success": False}))
        self.assertFalse(cls._is_ok_response({}))

    def test_is_ok_response_true_for_code_200(self):
        cls = self.connector_cls
        self.assertTrue(cls._is_ok_response({"code": "200"}))
        self.assertTrue(cls._is_ok_response({"code": 200}))
        self.assertFalse(cls._is_ok_response({"code": "404"}))

    def test_account_from_response_with_data_dict(self):
        cls = self.connector_cls
        result = cls._account_from_response({"data": {"balance": "100"}})
        self.assertEqual({"balance": "100"}, result)

    def test_account_from_response_with_accounts_list(self):
        cls = self.connector_cls
        result = cls._account_from_response({"accounts": [{"id": 1}]})
        self.assertEqual({"id": 1}, result)

    def test_account_from_response_returns_none_for_missing_keys(self):
        cls = self.connector_cls
        self.assertIsNone(cls._account_from_response({}))
        self.assertIsNone(cls._account_from_response({"accounts": []}))

    def test_client_order_index_from_order_id_is_deterministic_and_non_negative(self):
        cls = self.connector_cls
        idx1 = cls._client_order_index_from_order_id("HBOT-1234")
        idx2 = cls._client_order_index_from_order_id("HBOT-1234")
        self.assertEqual(idx1, idx2)
        self.assertIsInstance(idx1, int)
        self.assertGreaterEqual(idx1, 0)

    # ---------------------------------------------------------------------------
    # Simple property accessor tests
    # ---------------------------------------------------------------------------

    def test_name_and_domain_return_domain_string(self):
        self.assertEqual("lighter_perpetual", self.connector.name)
        self.assertEqual("lighter_perpetual", self.connector.domain)

    def test_client_order_id_max_length_is_32(self):
        self.assertEqual(32, self.connector.client_order_id_max_length)

    def test_client_order_id_prefix_is_hbot(self):
        self.assertEqual("HBOT", self.connector.client_order_id_prefix)

    def test_request_path_properties(self):
        import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_constants as C

        self.assertEqual(C.EXCHANGE_INFO_PATH_URL, self.connector.trading_rules_request_path)
        self.assertEqual(C.EXCHANGE_INFO_PATH_URL, self.connector.trading_pairs_request_path)
        self.assertEqual(C.GET_PRICES_PATH_URL, self.connector.check_network_request_path)

    def test_trading_pairs_returns_initialized_list(self):
        self.assertEqual(["BTC-USDC"], self.connector.trading_pairs)

    def test_is_cancel_synchronous_is_true(self):
        self.assertTrue(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_is_trading_required_returns_flag(self):
        self.assertFalse(self.connector.is_trading_required)

    def test_funding_fee_poll_interval_is_120(self):
        self.assertEqual(120, self.connector.funding_fee_poll_interval)

    def test_supported_order_types_includes_limit_limit_maker_and_market(self):
        from hummingbot.core.data_type.common import OrderType

        order_types = self.connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, order_types)
        self.assertIn(OrderType.MARKET, order_types)
        self.assertIn(OrderType.LIMIT_MAKER, order_types)

    def test_supported_position_modes_is_oneway(self):
        from hummingbot.core.data_type.common import PositionMode

        modes = self.connector.supported_position_modes()
        self.assertEqual([PositionMode.ONEWAY], modes)

    def test_collateral_tokens_are_usdc(self):
        self.assertEqual("USDC", self.connector.get_buy_collateral_token("BTC-USDC"))
        self.assertEqual("USDC", self.connector.get_sell_collateral_token("BTC-USDC"))

    # ---------------------------------------------------------------------------
    # API key / account index helpers
    # ---------------------------------------------------------------------------

    def test_rest_api_key_returns_api_secret_when_api_key_non_numeric_and_secret_set(self):
        self.connector.api_key = "pub_key_text"
        self.connector.api_secret = "secret_string"
        self.assertEqual("secret_string", self.connector.rest_api_key)

    def test_rest_api_key_returns_api_key_when_numeric(self):
        self.connector.api_key = "42"
        self.assertEqual("42", self.connector.rest_api_key)

    def test_rest_api_key_returns_api_key_when_secret_empty(self):
        self.connector.api_key = "public_key"
        self.connector.api_secret = ""
        self.assertEqual("public_key", self.connector.rest_api_key)

    def test_api_host_for_signer_strips_api_path(self):
        host = self.connector._api_host_for_signer()
        self.assertIn("mainnet.zklighter.elliot.ai", host)
        self.assertNotIn("/api/v1", host)

    def test_get_account_index_returns_int(self):
        self.connector.account_index = "237600"
        self.assertEqual(237600, self.connector._get_account_index())

    def test_get_account_index_raises_for_invalid_string(self):
        self.connector.account_index = "not_a_number"
        with self.assertRaises(ValueError):
            self.connector._get_account_index()

    def test_account_query_params_returns_expected_dict(self):
        self.connector.account_index = "237600"
        params = self.connector._account_query_params()
        self.assertEqual({"by": "index", "value": "237600"}, params)

    async def test_refresh_market_metadata_updates_maps_for_perp_only(self):
        self.connector._api_get = AsyncMock(return_value={
            "order_books": [
                {
                    "market_type": "spot",
                    "symbol": "BTC",
                    "market_id": 1,
                    "supported_size_decimals": 3,
                    "supported_price_decimals": 2,
                },
                {
                    "market_type": "perp",
                    "symbol": "ETH",
                    "market_id": 2,
                    "supported_size_decimals": 4,
                    "supported_price_decimals": 1,
                },
            ]
        })

        await self.connector._refresh_market_metadata()

        self.assertNotIn("BTC", self.connector._market_id_by_symbol)
        self.assertEqual(2, self.connector._market_id_by_symbol["ETH"])
        self.assertEqual(4, self.connector._size_decimals_by_symbol["ETH"])
        self.assertEqual(1, self.connector._price_decimals_by_symbol["ETH"])

    async def test_get_market_spec_uses_cache_without_refresh(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._market_id_by_symbol["BTC"] = 11
        self.connector._size_decimals_by_symbol["BTC"] = 3
        self.connector._price_decimals_by_symbol["BTC"] = 2
        self.connector._refresh_market_metadata = AsyncMock()

        market_id, size_decimals, price_decimals, symbol = await self.connector._get_market_spec("BTC-USDC")

        self.assertEqual(11, market_id)
        self.assertEqual(3, size_decimals)
        self.assertEqual(2, price_decimals)
        self.assertEqual("BTC", symbol)
        self.connector._refresh_market_metadata.assert_not_awaited()

    async def test_get_market_spec_raises_when_symbol_missing_after_refresh(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="DOGE")
        self.connector._refresh_market_metadata = AsyncMock()

        with self.assertRaises(ValueError):
            await self.connector._get_market_spec("DOGE-USDC")

        self.connector._refresh_market_metadata.assert_awaited_once()

    async def test_api_request_url_uses_private_rest_url(self):
        import hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_web_utils as web_utils

        path = "/api/v1/test"
        expected = web_utils.private_rest_url(path, domain=self.connector.domain)

        result = await self.connector._api_request_url(path)

        self.assertEqual(expected, result)

    def test_is_request_exception_not_related_to_time_synchronizer(self):
        result = self.connector._is_request_exception_related_to_time_synchronizer(Exception("any error"))
        self.assertFalse(result)

    def test_is_order_not_found_during_status_update_error_matches(self):
        self.assertTrue(self.connector._is_order_not_found_during_status_update_error(Exception("Order not found")))
        self.assertFalse(self.connector._is_order_not_found_during_status_update_error(Exception("Network error")))

    def test_is_order_not_found_during_cancelation_error_matches(self):
        self.assertTrue(self.connector._is_order_not_found_during_cancelation_error(Exception('{"code":5}')))
        self.assertFalse(self.connector._is_order_not_found_during_cancelation_error(Exception("network timeout")))

    # ---------------------------------------------------------------------------
    # Price record helpers
    # ---------------------------------------------------------------------------

    def test_get_lighter_price_returns_none_for_unknown_pair(self):
        result = self.connector.get_LIGHTER_price("ETH-USDC")
        self.assertIsNone(result)

    def test_get_lighter_price_returns_none_for_unset_btc(self):
        result = self.connector.get_LIGHTER_price("BTC-USDC")
        self.assertIsNone(result)

    def test_get_lighter_finance_trade_id_builds_expected_string(self):
        trade_id = self.connector.get_LIGHTER_finance_trade_id(
            order_id=123456,
            timestamp=1700000000.0,
            fill_base_amount=Decimal("0.5"),
            fill_price=Decimal("50000"),
        )
        self.assertEqual("123456_1700000000.0_0.5_50000", trade_id)

    def test_round_fee_rounds_to_6_decimal_places(self):
        result = self.connector.round_fee(Decimal("0.123456789"))
        self.assertAlmostEqual(0.123457, float(result), places=5)

    # ---------------------------------------------------------------------------
    # Async method tests (safe mocked paths)
    # ---------------------------------------------------------------------------

    async def test_get_last_traded_price_returns_close_price(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": [{"symbol": "BTC", "mid": "50123.5", "mark": "50000"}],
        })

        result = await self.connector._get_last_traded_price("BTC-USDC")
        self.assertAlmostEqual(50123.5, result)

    async def test_get_last_traded_price_falls_back_to_candles_when_prices_endpoint_has_no_symbol(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._api_get = AsyncMock(side_effect=[
            {"success": True, "data": [{"symbol": "ETH", "mid": "3000"}]},
            {"data": [{"c": "50123.5", "o": "50000"}]},
        ])

        result = await self.connector._get_last_traded_price("BTC-USDC")

        self.assertAlmostEqual(50123.5, result)

    async def test_get_last_traded_price_returns_zero_for_empty_candles(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._api_get = AsyncMock(side_effect=[
            {"success": True, "data": []},
            {"data": []},
        ])

        result = await self.connector._get_last_traded_price("BTC-USDC")
        self.assertEqual(0.0, result)

    async def test_modify_order_uses_native_sdk(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "1234"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.current_timestamp = 1700000000.0

        mock_tx_response = MagicMock()
        mock_tx_response.code = 200

        mock_signer = MagicMock()
        mock_signer.modify_order = AsyncMock(return_value=(MagicMock(), mock_tx_response, None))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_market_spec = AsyncMock(return_value=(0, 2, 2, None))
        self.connector._get_api_key_index = MagicMock(return_value=2)

        exchange_id, ts = await self.connector._modify_order(
            tracked_order=tracked_order,
            new_price=Decimal("50000"),
            new_amount=Decimal("0.1"),
        )

        self.assertEqual("1234", exchange_id)
        mock_signer.modify_order.assert_awaited_once_with(
            market_index=0,
            order_index=1234,
            base_amount=10,
            price=5000000,
            api_key_index=2,
        )

    async def test_modify_order_raises_when_sdk_returns_error(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "1234"
        tracked_order.trading_pair = "BTC-USDC"

        mock_signer = MagicMock()
        mock_signer.modify_order = AsyncMock(return_value=(None, None, "sign error"))
        self.connector._get_lighter_signer_client = MagicMock(return_value=mock_signer)
        self.connector._get_market_spec = AsyncMock(return_value=(0, 2, 2, None))
        self.connector._get_api_key_index = MagicMock(return_value=2)

        with self.assertRaises(IOError):
            await self.connector._modify_order(
                tracked_order=tracked_order,
                new_price=Decimal("50000"),
                new_amount=Decimal("0.1"),
            )

    def test_extract_ticker_price_prefers_last_trade_then_mid_mark_oracle(self):
        extractor = self.connector_cls._extract_ticker_price

        self.assertEqual(Decimal("12.3"), extractor({"last_trade_price": "12.3", "mid": "11"}))
        self.assertEqual(Decimal("11"), extractor({"mid": "11", "mark": "10"}))
        self.assertEqual(Decimal("10"), extractor({"mark": "10", "oracle": "9"}))
        self.assertEqual(Decimal("9"), extractor({"oracle": "9"}))
        self.assertIsNone(extractor({}))

    def test_extract_liquidation_price_reads_rest_and_ws_shapes(self):
        extractor = self.connector_cls._extract_liquidation_price

        self.assertEqual(Decimal("100"), extractor({"liquidation_price": "100"}))
        self.assertEqual(Decimal("200"), extractor({"l": "200"}))
        self.assertIsNone(extractor({"l": ""}))
        self.assertIsNone(extractor({}))

    def test_warn_if_position_near_liquidation_emits_warning(self):
        mock_logger = MagicMock()
        with patch.object(self.connector, "logger", return_value=mock_logger):
            from hummingbot.core.data_type.common import PositionSide

            self.connector._warn_if_position_near_liquidation(
                trading_pair="BTC-USDC",
                position_side=PositionSide.LONG,
                mark_price=Decimal("100"),
                liquidation_price=Decimal("96"),
            )

        mock_logger.warning.assert_called()

    async def test_update_trading_fees_updates_maker_and_taker_fee(self):
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": {"fee_level": 1, "maker_fee": "0.0002", "taker_fee": "0.0005"},
        })

        await self.connector._update_trading_fees()

        self.assertIn("BTC-USDC", self.connector._trading_fees)
        schema = self.connector._trading_fees["BTC-USDC"]
        self.assertEqual(Decimal("0.0002"), schema.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.0005"), schema.taker_percent_fee_decimal)

    async def test_update_trading_fees_skips_on_api_failure(self):
        self.connector._api_get = AsyncMock(return_value={"success": False})

        await self.connector._update_trading_fees()

        self.assertEqual({}, self.connector._trading_fees)

    async def test_update_trading_fees_skips_when_fees_absent_from_data(self):
        self.connector._api_get = AsyncMock(return_value={"success": True, "data": {"fee_level": 0}})

        await self.connector._update_trading_fees()

        self.assertEqual({}, self.connector._trading_fees)

    async def test_request_order_status_returns_order_update_for_filled(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "315293920"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        self.connector._api_get = AsyncMock(return_value={"data": [{"order_status": "filled", "created_at": 1700000000000}]})

        from hummingbot.core.data_type.in_flight_order import OrderState

        order_update = await self.connector._request_order_status(tracked_order)

        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual("315293920", order_update.exchange_order_id)
        self.assertEqual(OrderState.FILLED, order_update.new_state)

    async def test_request_order_status_raises_on_empty_data(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "999"
        self.connector._api_get = AsyncMock(return_value={"data": []})

        with self.assertRaises(IOError):
            await self.connector._request_order_status(tracked_order)

    async def test_request_order_status_raises_on_unknown_status(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "999"
        self.connector._api_get = AsyncMock(return_value={"data": [{"order_status": "unknown_xyz", "created_at": 0}]})

        with self.assertRaises(IOError):
            await self.connector._request_order_status(tracked_order)

    async def test_set_trading_pair_leverage_returns_success(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._api_post = AsyncMock(return_value={"success": True})

        success, msg = await self.connector._set_trading_pair_leverage("BTC-USDC", 10)

        self.assertTrue(success)
        self.assertEqual("", msg)

    async def test_set_trading_pair_leverage_returns_error_message_on_failure(self):
        self.connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC")
        self.connector._api_post = AsyncMock(return_value={"success": False, "error": "leverage too high", "code": 429})

        success, msg = await self.connector._set_trading_pair_leverage("BTC-USDC", 1000)

        self.assertFalse(success)
        self.assertIn("leverage too high", msg)

    async def test_trading_pair_position_mode_set_always_returns_true(self):
        from hummingbot.core.data_type.common import PositionMode

        success, msg = await self.connector._trading_pair_position_mode_set(PositionMode.ONEWAY, "BTC-USDC")
        self.assertTrue(success)
        self.assertEqual("", msg)

    async def test_get_all_pairs_prices_returns_list(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=lambda symbol: f"{symbol}-USDC")
        self.connector._api_get = AsyncMock(return_value={
            "success": True,
            "data": [
                {"symbol": "BTC", "mark": "50000"},
                {"symbol": "ETH", "mark": "3000"},
            ],
        })

        results = await self.connector.get_all_pairs_prices()

        self.assertEqual(2, len(results))
        self.assertEqual("BTC-USDC", results[0]["trading_pair"])
        self.assertEqual("50000", results[0]["price"])

    async def test_get_all_pairs_prices_returns_empty_on_api_failure(self):
        self.connector._api_get = AsyncMock(return_value={"success": False})

        results = await self.connector.get_all_pairs_prices()

        self.assertEqual([], results)

    # ---------------------------------------------------------------------------
    # Trading rules + symbol map
    # ---------------------------------------------------------------------------

    async def test_format_trading_rules_from_order_books(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=lambda symbol: f"{symbol}-USDC")
        exchange_info = {
            "order_books": [
                {
                    "market_type": "perp",
                    "symbol": "BTC",
                    "market_id": "0",
                    "supported_size_decimals": 5,
                    "supported_price_decimals": 1,
                    "min_quote_amount": "10",
                },
                {
                    "market_type": "spot",
                    "symbol": "ETH",
                    "market_id": "1",
                    "supported_size_decimals": 4,
                    "supported_price_decimals": 2,
                    "min_quote_amount": "5",
                },
            ]
        }

        rules = await self.connector._format_trading_rules(exchange_info)

        self.assertEqual(1, len(rules))
        self.assertEqual("BTC-USDC", rules[0].trading_pair)
        self.assertEqual(Decimal("1e-5"), rules[0].min_order_size)
        self.assertEqual(Decimal("1e-1"), rules[0].min_price_increment)

    async def test_format_trading_rules_from_data_list(self):
        self.connector.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=lambda symbol: f"{symbol}-USDC")
        exchange_info = {
            "data": [
                {
                    "symbol": "ETH",
                    "lot_size": "0.001",
                    "tick_size": "0.01",
                    "min_order_size": "5",
                }
            ]
        }

        rules = await self.connector._format_trading_rules(exchange_info)

        self.assertEqual(1, len(rules))
        self.assertEqual("ETH-USDC", rules[0].trading_pair)
        self.assertEqual(Decimal("0.001"), rules[0].min_order_size)
        self.assertEqual(Decimal("0.01"), rules[0].min_price_increment)

    def test_initialize_trading_pair_symbols_from_order_books_populates_market_map(self):
        self.connector._set_trading_pair_symbol_map = MagicMock()
        exchange_info = {
            "order_books": [
                {
                    "market_type": "perp",
                    "symbol": "BTC",
                    "market_id": "1",
                    "supported_size_decimals": 5,
                    "supported_price_decimals": 1,
                },
                {
                    "market_type": "spot",
                    "symbol": "ETH",
                    "market_id": "2",
                    "supported_size_decimals": 4,
                    "supported_price_decimals": 2,
                },
            ]
        }

        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)

        self.assertEqual(1, self.connector._market_id_by_symbol.get("BTC"))
        self.assertNotIn("ETH", self.connector._market_id_by_symbol)
        self.connector._set_trading_pair_symbol_map.assert_called_once()

    def test_initialize_trading_pair_symbols_from_data_list(self):
        self.connector._set_trading_pair_symbol_map = MagicMock()
        exchange_info = {"data": [{"symbol": "ETH"}]}

        self.connector._initialize_trading_pair_symbols_from_exchange_info(exchange_info)

        self.connector._set_trading_pair_symbol_map.assert_called_once()

    # ---------------------------------------------------------------------------
    # Position / trade normalization helper tests
    # ---------------------------------------------------------------------------

    def test_normalized_position_entries_passthrough_for_short_form_data(self):
        event = {"data": [{"s": "BTC", "d": "bid", "a": "0.5", "p": "50000"}]}

        result = self.connector_cls._normalized_position_entries_from_event(event)

        self.assertEqual(1, len(result))
        self.assertEqual("BTC", result[0]["s"])

    def test_normalized_position_entries_converts_positions_dict(self):
        event = {
            "positions": {
                "0": {
                    "symbol": "ETH",
                    "sign": -1,
                    "position": "1.0",
                    "avg_entry_price": "2000",
                    "unrealized_pnl": "5.0",
                }
            }
        }

        result = self.connector_cls._normalized_position_entries_from_event(event)

        self.assertEqual(1, len(result))
        self.assertEqual("ETH", result[0]["s"])
        self.assertEqual("ask", result[0]["d"])

    def test_normalized_position_entries_skips_zero_amount(self):
        event = {
            "positions": {
                "0": {
                    "symbol": "BTC",
                    "sign": 1,
                    "position": "0",
                    "avg_entry_price": "50000",
                }
            }
        }

        result = self.connector_cls._normalized_position_entries_from_event(event)

        self.assertEqual(0, len(result))

    def test_normalized_trade_entries_passthrough_for_short_form_data(self):
        event = {"data": [{"i": "123", "p": "100", "a": "0.5"}]}

        result = self.connector._normalized_trade_entries_from_event(event)

        self.assertEqual(1, len(result))
        self.assertEqual("123", result[0]["i"])

    def test_normalized_trade_entries_from_account_all_own_bid(self):
        self.connector.account_index = "237600"
        event = {
            "trades": {
                "0": [{
                    "bid_client_id_str": "1774621023",
                    "bid_account_id": 237600,
                    "ask_account_id": 702389,
                    "is_maker_ask": True,
                    "taker_fee": 280,
                    "maker_fee": 28,
                    "price": "1983.11",
                    "size": "0.0051",
                    "usd_amount": "10.1",
                    "trade_id_str": "16734837600",
                    "timestamp": 1774621024363,
                }]
            }
        }

        result = self.connector._normalized_trade_entries_from_event(event)

        self.assertEqual(1, len(result))
        self.assertEqual("1774621023", result[0]["i"])

    def test_normalized_trade_entries_skips_unrelated_trades(self):
        self.connector.account_index = "237600"
        event = {
            "trades": {
                "0": [{
                    "bid_client_id_str": "999",
                    "bid_account_id": 111111,
                    "ask_account_id": 222222,
                    "is_maker_ask": False,
                    "taker_fee": 100,
                    "maker_fee": 10,
                    "price": "100",
                    "size": "1.0",
                    "usd_amount": "100",
                    "timestamp": 1700000000000,
                }]
            }
        }

        result = self.connector._normalized_trade_entries_from_event(event)

        self.assertEqual(0, len(result))

    def test_round_amount_rounds_to_lot_size(self):
        """Test that round_amount quantizes to the min_base_amount_increment from trading rules"""
        from hummingbot.connector.trading_rule import TradingRule

        # Setup trading rules with a specific lot size
        trading_pair = "BTC-USDC"
        self.connector._trading_rules = {
            trading_pair: TradingRule(
                trading_pair=trading_pair,
                min_order_size=Decimal("0.001"),
                max_order_size=Decimal("100"),
                min_price_increment=Decimal("0.01"),
                min_base_amount_increment=Decimal("0.001"),
            )
        }

        # Test rounding up
        result = self.connector.round_amount(trading_pair, Decimal("1.2345"))
        self.assertEqual(Decimal("1.234"), result)

        # Test rounding down
        result = self.connector.round_amount(trading_pair, Decimal("0.9994"))
        self.assertEqual(Decimal("0.999"), result)
