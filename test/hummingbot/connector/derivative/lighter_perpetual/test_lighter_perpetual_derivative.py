import unittest
import sys
import types
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


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
            from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_derivative import LighterPerpetualDerivative
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

    def test_get_api_key_index_raises_for_non_numeric_config(self):
        self.connector.api_key = "not-a-number"
        self.connector.api_secret = "not-a-number"
        self.connector.api_key_index = ""

        with self.assertRaises(ValueError):
            self.connector._get_api_key_index()

    async def test_fetch_or_create_api_config_key_resolves_index_from_api_keys(self):
        self.connector.api_key = "abc_public_key"
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

    def test_get_signer_private_key_prefers_explicit_private_key(self):
        self.connector.private_key = "0xsigner"
        self.connector.api_key = "public"
        self.connector.api_secret = "secret"

        self.assertEqual("0xsigner", self.connector._get_signer_private_key())

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

    async def test_process_account_order_updates_ws_event_message_updates_tracked_order(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        self.connector._order_tracker.all_updatable_orders = {"HBOT-1": tracked_order}
        self.connector._order_tracker.process_order_update = MagicMock()

        await self.connector._process_account_order_updates_ws_event_message({
            "data": [{"i": 123, "os": "filled", "ut": 1700000000000}],
        })

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args.args[0]
        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual("123", order_update.exchange_order_id)

    async def test_process_account_order_updates_ws_event_message_ignores_unknown_order(self):
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

    async def test_process_account_trades_ws_event_message_processes_tracked_trade(self):
        tracked_order = MagicMock()
        tracked_order.exchange_order_id = "123"
        tracked_order.client_order_id = "HBOT-1"
        tracked_order.trading_pair = "BTC-USDC"
        tracked_order.quote_asset = "USDC"
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
            api_key_index=4,
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
