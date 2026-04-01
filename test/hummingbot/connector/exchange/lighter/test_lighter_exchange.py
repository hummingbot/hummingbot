import sys
import types
import unittest
from decimal import Decimal
from enum import Enum
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.common import OrderType
from hummingbot.core.web_assistant.connections.data_types import RESTMethod
from hummingbot.core.data_type.trade_fee import TradeFeeSchema

if "hummingbot.core.data_type.limit_order" not in sys.modules:
    fake_limit_order = types.ModuleType("hummingbot.core.data_type.limit_order")

    class LimitOrder:
        pass

    fake_limit_order.LimitOrder = LimitOrder
    sys.modules["hummingbot.core.data_type.limit_order"] = fake_limit_order

if "hummingbot.core.data_type.order_book" not in sys.modules:
    fake_order_book = types.ModuleType("hummingbot.core.data_type.order_book")

    class OrderBook:
        def apply_snapshot(self, bids, asks, update_id):
            _ = bids
            _ = asks
            _ = update_id

    fake_order_book.OrderBook = OrderBook
    sys.modules["hummingbot.core.data_type.order_book"] = fake_order_book

if "hummingbot.connector.exchange_base" not in sys.modules:
    fake_exchange_base = types.ModuleType("hummingbot.connector.exchange_base")

    class ExchangeBase:
        def __init__(self, *args, **kwargs):
            pass

    fake_exchange_base.ExchangeBase = ExchangeBase
    sys.modules["hummingbot.connector.exchange_base"] = fake_exchange_base

if "hummingbot.connector.trading_rule" not in sys.modules:
    fake_trading_rule = types.ModuleType("hummingbot.connector.trading_rule")

    class TradingRule:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    fake_trading_rule.TradingRule = TradingRule
    sys.modules["hummingbot.connector.trading_rule"] = fake_trading_rule

if "hummingbot.core.network_iterator" not in sys.modules:
    fake_network_iterator = types.ModuleType("hummingbot.core.network_iterator")

    class NetworkStatus(Enum):
        STOPPED = 0
        NOT_CONNECTED = 1
        CONNECTED = 2

    fake_network_iterator.NetworkStatus = NetworkStatus
    sys.modules["hummingbot.core.network_iterator"] = fake_network_iterator

try:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
    from hummingbot.core.data_type.in_flight_order import OrderState
    _LIGHTER_EXCHANGE_AVAILABLE = True
except ModuleNotFoundError:
    _LIGHTER_EXCHANGE_AVAILABLE = False


@unittest.skipUnless(_LIGHTER_EXCHANGE_AVAILABLE, "Core exchange runtime modules are unavailable in this local environment")
class LighterExchangeTests(IsolatedAsyncioWrapperTestCase):
    def test_init_and_properties(self):
        with patch("hummingbot.connector.exchange.lighter.lighter_exchange.ExchangePyBase.__init__", lambda self: None):
            exchange = LighterExchange(
                lighter_api_key="7",
                lighter_api_secret="sec",
                lighter_account_index="693751",
                lighter_private_key="pk",
                trading_pairs=["ETH-USDC"],
                trading_required=False,
            )

        self.assertEqual("lighter", exchange.name)
        self.assertEqual("lighter", exchange.domain)
        self.assertEqual(["ETH-USDC"], exchange.trading_pairs)
        self.assertFalse(exchange.is_trading_required)
        self.assertTrue(exchange.is_cancel_request_in_exchange_synchronous)
        self.assertEqual("https://mainnet.zklighter.elliot.ai", exchange._api_host_for_signer())

    def test_supported_order_types_and_request_paths(self):
        exchange = object.__new__(LighterExchange)
        exchange._domain = "lighter"
        self.assertEqual([OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.MARKET], exchange.supported_order_types())
        self.assertEqual("/orderBooks", exchange.trading_rules_request_path)
        self.assertEqual("/orderBooks", exchange.trading_pairs_request_path)
        self.assertEqual("/", exchange.check_network_request_path)

    async def test_refresh_market_metadata_and_get_market_spec(self):
        exchange = object.__new__(LighterExchange)
        exchange._market_id_by_symbol = {}
        exchange._size_decimals_by_symbol = {}
        exchange._price_decimals_by_symbol = {}
        exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value="ETH/USDC")
        exchange._api_get = AsyncMock(
            return_value={
                "order_books": [
                    {
                        "symbol": "ETH/USDC",
                        "market_type": "spot",
                        "market_id": 2048,
                        "supported_size_decimals": 4,
                        "supported_price_decimals": 2,
                    }
                ]
            }
        )

        await exchange._refresh_market_metadata()
        spec = await exchange._get_market_spec("ETH-USDC")
        self.assertEqual((2048, 4, 2, "ETH/USDC"), spec)

    async def test_get_market_spec_raises_when_missing(self):
        exchange = object.__new__(LighterExchange)
        exchange._market_id_by_symbol = {}
        exchange._size_decimals_by_symbol = {}
        exchange._price_decimals_by_symbol = {}
        exchange.exchange_symbol_associated_to_pair = AsyncMock(return_value="MISSING")
        exchange._refresh_market_metadata = AsyncMock()

        with self.assertRaises(ValueError):
            await exchange._get_market_spec("ETH-USDC")

    async def test_place_order_and_cancel_success(self):
        exchange = object.__new__(LighterExchange)
        exchange.current_timestamp = 1700000000
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._client_order_index_from_order_id = lambda order_id: 999
        exchange._get_api_key_index = lambda: 7

        signer_client = type(
            "SignerClient",
            (),
            {
                "ORDER_TYPE_LIMIT": 1,
                "ORDER_TYPE_MARKET": 2,
                "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
                "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
                "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
                "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
                "DEFAULT_IOC_EXPIRY": 1001,
            },
        )()
        signer_client.create_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 200})(), None))
        signer_client.cancel_order = AsyncMock(return_value=(None, type("Resp", (), {"code": 200})(), None))
        exchange._get_lighter_signer_client = lambda: signer_client

        exchange_order_id, ts = await exchange._place_order(
            order_id="HBOT-A",
            trading_pair="ETH-USDC",
            amount=Decimal("1"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("10"),
        )
        result = await exchange._place_cancel("HBOT-A", type("Tracked", (), {"trading_pair": "ETH-USDC", "exchange_order_id": "42"})())

        self.assertEqual("999", exchange_order_id)
        self.assertEqual(1700000000, ts)
        self.assertTrue(result)

    async def test_place_order_and_cancel_errors(self):
        exchange = object.__new__(LighterExchange)
        exchange.current_timestamp = 1700000000
        exchange._get_market_spec = AsyncMock(return_value=(2048, 2, 2, "ETH/USDC"))
        exchange._client_order_index_from_order_id = lambda order_id: 111
        exchange._get_api_key_index = lambda: 7

        signer_client = type(
            "SignerClient",
            (),
            {
                "ORDER_TYPE_LIMIT": 1,
                "ORDER_TYPE_MARKET": 2,
                "ORDER_TIME_IN_FORCE_GOOD_TILL_TIME": 10,
                "ORDER_TIME_IN_FORCE_IMMEDIATE_OR_CANCEL": 11,
                "ORDER_TIME_IN_FORCE_POST_ONLY": 12,
                "DEFAULT_28_DAY_ORDER_EXPIRY": 1000,
                "DEFAULT_IOC_EXPIRY": 1001,
            },
        )()
        signer_client.create_order = AsyncMock(return_value=(None, None, "err"))
        signer_client.cancel_order = AsyncMock(return_value=(None, None, "err"))
        exchange._get_lighter_signer_client = lambda: signer_client

        with self.assertRaises(IOError):
            await exchange._place_order(
                order_id="HBOT-B",
                trading_pair="ETH-USDC",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                price=Decimal("10"),
            )

        with self.assertRaises(IOError):
            await exchange._place_cancel("HBOT-B", type("Tracked", (), {"trading_pair": "ETH-USDC", "exchange_order_id": "42"})())

    async def test_api_request_and_get_last_traded_prices(self):
        exchange = object.__new__(LighterExchange)
        exchange._domain = "lighter"
        exchange._api_key = "k"
        exchange._web_assistants_factory = type("Factory", (), {"get_rest_assistant": AsyncMock()})()
        rest = type("Rest", (), {})()
        rest.execute_request = AsyncMock(return_value={"ok": True})
        exchange._web_assistants_factory.get_rest_assistant = AsyncMock(return_value=rest)

        response = await exchange._api_request(path_url="/orderBooks", method=RESTMethod.GET, params={"a": 1}, is_auth_required=True)
        self.assertEqual({"ok": True}, response)

        exchange._api_request = AsyncMock(
            return_value={
                "data": [
                    {"symbol": "ETH/USDC", "index_price": "100.5"},
                    {"symbol": "BTC/USDC", "index_price": "200.5"},
                ]
            }
        )
        exchange.trading_pair_associated_to_exchange_symbol = AsyncMock(side_effect=["ETH-USDC", "BTC-USDC"])
        prices = await exchange.get_last_traded_prices(["ETH-USDC"])
        self.assertEqual({"ETH-USDC": 100.5}, prices)

    async def test_status_polling_loop_fetch_updates(self):
        exchange = object.__new__(LighterExchange)
        exchange._update_balances = AsyncMock()
        exchange._update_order_status = AsyncMock()
        exchange._update_lost_orders_status = AsyncMock()

        await exchange._status_polling_loop_fetch_updates()
        self.assertEqual(1, exchange._update_balances.await_count)
        self.assertEqual(1, exchange._update_order_status.await_count)
        self.assertEqual(1, exchange._update_lost_orders_status.await_count)
    def test_hb_pair_from_symbol_variants(self):
        self.assertEqual("ETH-USDC", LighterExchange._hb_pair_from_symbol("ETH/USDC"))
        self.assertEqual("BTC-USDC", LighterExchange._hb_pair_from_symbol("BTC-USDC"))

    def test_client_order_index_from_order_id_is_stable(self):
        idx_1 = LighterExchange._client_order_index_from_order_id("HBOT-1")
        idx_2 = LighterExchange._client_order_index_from_order_id("HBOT-1")

        self.assertEqual(idx_1, idx_2)
        self.assertGreaterEqual(idx_1, 0)
        self.assertLessEqual(idx_1, 0x7FFFFFFFFFFFFFFF)

    def test_get_signer_private_key_precedence_and_validation(self):
        exchange = object.__new__(LighterExchange)
        exchange._private_key = "private"
        exchange._api_key = "111"
        exchange._api_secret = "222"
        self.assertEqual("private", exchange._get_signer_private_key())

        exchange._private_key = ""
        exchange._api_key = "0xabc"
        exchange._api_secret = "123"
        self.assertEqual("0xabc", exchange._get_signer_private_key())

        exchange._api_key = "123"
        exchange._api_secret = "0xdef"
        self.assertEqual("0xdef", exchange._get_signer_private_key())

        exchange._api_key = "123"
        exchange._api_secret = "456"
        with self.assertRaises(ValueError):
            exchange._get_signer_private_key()

    def test_get_api_key_index_and_account_index(self):
        exchange = object.__new__(LighterExchange)
        exchange._api_key = "7"
        exchange._api_secret = "999"
        exchange._account_index = "42"
        self.assertEqual(7, exchange._get_api_key_index())
        self.assertEqual(42, exchange._get_account_index())

        exchange._api_key = "key"
        exchange._api_secret = "8"
        self.assertEqual(8, exchange._get_api_key_index())

        exchange._api_key = "key"
        exchange._api_secret = "secret"
        with self.assertRaises(ValueError):
            exchange._get_api_key_index()

        exchange._account_index = "abc"
        with self.assertRaises(ValueError):
            exchange._get_account_index()

    def test_account_from_response_variants(self):
        self.assertEqual({"assets": []}, LighterExchange._account_from_response({"data": {"assets": []}}))
        self.assertEqual({"assets": [1]}, LighterExchange._account_from_response({"data": [{"assets": [1]}]}))
        self.assertEqual({"assets": [2]}, LighterExchange._account_from_response({"accounts": [{"assets": [2]}]}))

    def test_account_query_params(self):
        exchange = object.__new__(LighterExchange)
        exchange._account_index = "693751"
        self.assertEqual({"by": "index", "value": "693751"}, exchange._account_query_params())

    def test_is_ok_response(self):
        self.assertTrue(LighterExchange._is_ok_response({"success": True}))
        self.assertTrue(LighterExchange._is_ok_response({"code": 200}))
        self.assertFalse(LighterExchange._is_ok_response({"code": 500}))

    def test_process_balance_message_from_account(self):
        exchange = object.__new__(LighterExchange)
        exchange._account_balances = {}
        exchange._account_available_balances = {}

        exchange._process_balance_message_from_account(
            {
                "assets": [
                    {"symbol": "USDC", "balance": "10", "locked_balance": "2"},
                    {"symbol": "ETH", "balance": "1.5", "locked_balance": "0.5"},
                ]
            }
        )

        self.assertEqual(Decimal("10"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("8"), exchange._account_available_balances["USDC"])
        self.assertEqual(Decimal("1.0"), exchange._account_available_balances["ETH"])

    def test_order_update_from_raw_message(self):
        exchange = object.__new__(LighterExchange)
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-1",
                "exchange_order_id": "42",
                "trading_pair": "ETH-USDC",
            },
        )()
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_updatable_orders": {"HBOT-1": tracked_order},
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()

        order_update = exchange._order_update_from_raw_message(
            {"client_order_id": "HBOT-1", "order_status": "canceled", "updated_at": 1700000000}
        )

        self.assertIsNotNone(order_update)
        self.assertEqual("HBOT-1", order_update.client_order_id)
        self.assertEqual(OrderState.CANCELED, order_update.new_state)

    def test_trade_update_from_raw_message(self):
        exchange = object.__new__(LighterExchange)
        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-2",
                "exchange_order_id": "77",
                "trading_pair": "ETH-USDC",
                "quote_asset": "USDC",
                "trade_type": TradeType.BUY,
            },
        )()
        exchange.trade_fee_schema = lambda: TradeFeeSchema()
        exchange.current_timestamp = 1700000000
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "all_fillable_orders": {"HBOT-2": tracked_order},
                "all_fillable_orders_by_exchange_order_id": {"77": tracked_order},
            },
        )()

        trade_update = exchange._trade_update_from_raw_message(
            {
                "client_order_id": "HBOT-2",
                "order_id": "77",
                "trade_id": "t-1",
                "price": "2.5",
                "amount": "4",
                "created_at": 1700000000123,
            }
        )

        self.assertIsNotNone(trade_update)
        self.assertEqual("t-1", trade_update.trade_id)
        self.assertEqual(Decimal("2.5"), trade_update.fill_price)
        self.assertEqual(Decimal("4"), trade_update.fill_base_amount)
        self.assertEqual(Decimal("10"), trade_update.fill_quote_amount)

    async def test_format_trading_rules_filters_non_spot(self):
        exchange = object.__new__(LighterExchange)
        rules = await exchange._format_trading_rules(
            {
                "data": [
                    {"symbol": "ETH/USDC", "market_type": "spot", "supported_size_decimals": 3, "supported_price_decimals": 2},
                    {"symbol": "BTC/USDC", "market_type": "perp", "supported_size_decimals": 3, "supported_price_decimals": 2},
                ]
            }
        )
        self.assertEqual(1, len(rules))
        self.assertEqual("ETH-USDC", rules[0].trading_pair)

    async def test_request_order_status_empty_returns_current_state(self):
        exchange = object.__new__(LighterExchange)
        exchange.current_timestamp = 1700001234
        exchange._api_get = AsyncMock(return_value={"success": True, "data": []})

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-3",
                "exchange_order_id": "300",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual("HBOT-3", status.client_order_id)
        self.assertEqual(OrderState.OPEN, status.new_state)

    async def test_request_order_status_parses_state(self):
        exchange = object.__new__(LighterExchange)
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": [
                    {"created_at": 1, "order_status": "open"},
                    {"created_at": 2, "order_status": "canceled"},
                ],
            }
        )

        tracked_order = type(
            "TrackedOrder",
            (),
            {
                "client_order_id": "HBOT-4",
                "exchange_order_id": "301",
                "trading_pair": "ETH-USDC",
                "current_state": OrderState.OPEN,
            },
        )()

        status = await exchange._request_order_status(tracked_order)
        self.assertEqual(OrderState.CANCELED, status.new_state)

    async def test_update_balances_updates_and_removes_assets(self):
        exchange = object.__new__(LighterExchange)
        exchange._account_balances = {"OLD": Decimal("1")}
        exchange._account_available_balances = {"OLD": Decimal("1")}
        exchange._account_query_params = lambda: {"by": "index", "value": "1"}
        exchange._api_get = AsyncMock(
            return_value={
                "success": True,
                "data": {
                    "assets": [
                        {"symbol": "USDC", "balance": "12", "locked_balance": "2"},
                    ]
                },
            }
        )

        await exchange._update_balances()

        self.assertNotIn("OLD", exchange._account_balances)
        self.assertEqual(Decimal("12"), exchange._account_balances["USDC"])
        self.assertEqual(Decimal("10"), exchange._account_available_balances["USDC"])

    def test_initialize_trading_pair_symbols_from_exchange_info(self):
        exchange = object.__new__(LighterExchange)
        captured = {}
        exchange._set_trading_pair_symbol_map = lambda mapping: captured.update(mapping)

        exchange._initialize_trading_pair_symbols_from_exchange_info(
            {
                "data": [
                    {"symbol": "ETH/USDC", "market_type": "spot"},
                    {"symbol": "BTC/USDC", "market_type": "perp"},
                ]
            }
        )

        self.assertEqual({"ETH/USDC": "ETH-USDC"}, captured)

    async def test_request_order_fills_by_client_order_id_filters(self):
        exchange = object.__new__(LighterExchange)
        order = type("Order", (), {"client_order_id": "HBOT-5", "exchange_order_id": "500"})()
        exchange._request_order_fills_from_trades_api = AsyncMock(
            return_value=[
                {"client_order_id": "HBOT-0"},
                {"client_order_id": "HBOT-5"},
                {"clientOrderId": "HBOT-5"},
            ]
        )

        fills = await exchange._request_order_fills_by_client_order_id(order)
        self.assertEqual(2, len(fills))

    async def test_request_trade_fills(self):
        exchange = object.__new__(LighterExchange)
        exchange._account_index = "693751"
        exchange._domain = "lighter"
        exchange._api_get = AsyncMock(
            return_value={
                "data": [
                    {"history_id": "h1", "symbol": "ETH/USDC"},
                    {"trade_id": "t2", "symbol": "LIT/USDC"},
                ]
            }
        )

        fills = await exchange._request_trade_fills()
        self.assertEqual(2, len(fills))
        self.assertEqual("lighter", fills[0].market)
        self.assertEqual("h1", fills[0].exchange_trade_id)

    async def test_request_order_fills_from_trades_api_success_and_failure(self):
        exchange = object.__new__(LighterExchange)
        exchange._account_index = "693751"
        exchange._api_get = AsyncMock(return_value={"success": True, "data": [{"order_id": "1"}]})

        order = type("Order", (), {"exchange_order_id": "1"})()
        fills = await exchange._request_order_fills_from_trades_api(order)
        self.assertEqual(1, len(fills))

        exchange._api_get = AsyncMock(return_value={"success": False})
        fills = await exchange._request_order_fills_from_trades_api(order)
        self.assertEqual([], fills)

    async def test_request_order_fills_without_exchange_id(self):
        exchange = object.__new__(LighterExchange)
        order = type("Order", (), {"exchange_order_id": None})()
        fills = await exchange._request_order_fills(order)
        self.assertEqual([], fills)

    async def test_request_order_fills_and_fills_api_delegates(self):
        exchange = object.__new__(LighterExchange)
        order = type("Order", (), {"exchange_order_id": "99"})()
        exchange._request_order_fills_by_exchange_order_id = AsyncMock(return_value=[{"order_id": "99"}])
        exchange._request_order_fills_from_trades_api = AsyncMock(return_value=[{"order_id": "99"}])

        fills = await exchange._request_order_fills(order)
        fills2 = await exchange._request_order_fills_from_fills_api(order)
        self.assertEqual([{"order_id": "99"}], fills)
        self.assertEqual([{"order_id": "99"}], fills2)

    async def test_request_trade_updates_and_order_update_delegate(self):
        exchange = object.__new__(LighterExchange)
        order_1 = type("Order", (), {"id": "1"})()
        order_2 = type("Order", (), {"id": "2"})()
        trade_update = object()
        exchange._all_trade_updates_for_order = AsyncMock(side_effect=[[trade_update], []])
        exchange._request_order_status = AsyncMock(return_value="ORDER_UPDATE")

        updates = await exchange._request_trade_updates([order_1, order_2])
        order_update = await exchange._request_order_update(order_1)

        self.assertEqual([trade_update], updates)
        self.assertEqual("ORDER_UPDATE", order_update)

    async def test_execute_order_cancel_and_get_last_prices(self):
        exchange = object.__new__(LighterExchange)
        order = type("Order", (), {"client_order_id": "HBOT-8"})()
        exchange._place_cancel = AsyncMock(return_value=True)
        exchange.get_last_traded_prices = AsyncMock(return_value={"ETH-USDC": 1234.5})

        cancelled = await exchange._execute_order_cancel(order)
        last_price = await exchange._get_last_traded_price("ETH-USDC")
        last_trade_price = await exchange._get_last_trade_price("ETH-USDC")

        self.assertEqual("HBOT-8", cancelled)
        self.assertEqual(1234.5, last_price)
        self.assertEqual(1234.5, last_trade_price)

    async def test_create_order_fill_updates_and_fee_payment(self):
        exchange = object.__new__(LighterExchange)
        order = type("Order", (), {"client_order_id": "HBOT-9"})()
        exchange._all_trade_updates_for_order = AsyncMock(return_value=["a", "b"])

        updates = await exchange._create_order_fill_updates(order=order, exchange_order_id="1", fee=None)
        last_fee = await exchange._fetch_last_fee_payment("ETH-USDC")

        self.assertEqual(["a", "b"], updates)
        self.assertEqual((0, Decimal("0"), Decimal("0")), last_fee)

    async def test_get_all_pairs_prices(self):
        exchange = object.__new__(LighterExchange)
        exchange._api_get = AsyncMock(return_value={"data": [{"symbol": "ETH/USDC"}]})
        pairs = await exchange._get_all_pairs_prices()
        self.assertEqual([{"symbol": "ETH/USDC"}], pairs)

    async def test_create_trade_fill_updates(self):
        exchange = object.__new__(LighterExchange)
        exchange.current_timestamp = 1700000000
        exchange._get_fee = lambda **kwargs: "FEE"

        inflight_order = type(
            "InFlightOrder",
            (),
            {
                "client_order_id": "HBOT-10",
                "exchange_order_id": "500",
                "trading_pair": "ETH-USDC",
                "base_asset": "ETH",
                "quote_asset": "USDC",
                "order_type": "LIMIT",
                "trade_type": TradeType.BUY,
                "amount": Decimal("1"),
                "price": Decimal("100"),
            },
        )()

        fills_data = [{"trade_id": "t-1", "price": "100", "amount": "2", "quote_amount": "200", "timestamp": 1700000001}]
        updates = exchange._create_trade_fill_updates(inflight_order=inflight_order, fills_data=fills_data)

        self.assertEqual(1, len(updates))
        self.assertEqual("t-1", updates[0].trade_id)
        self.assertEqual(Decimal("200"), updates[0].fill_quote_amount)

    async def test_update_orders_with_error_handler(self):
        exchange = object.__new__(LighterExchange)
        processed = []
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_order_update": lambda self, update: processed.append(("order", update)),
                "process_trade_update": lambda self, update: processed.append(("trade", update)),
            },
        )()

        orders = ["o1", "o2", "o3"]

        async def fetch(order):
            if order == "o1":
                return "ORDER_UPDATE"
            if order == "o2":
                return [type("DummyTradeUpdate", (), {})()]
            raise RuntimeError("boom")

        handled = []

        async def on_error(order, err):
            handled.append((order, str(err)))

        await exchange._update_orders_with_error_handler(orders=orders, fetch_updates=fetch, error_handler=on_error)

        self.assertEqual(1, len(handled))
        self.assertEqual("o3", handled[0][0])

    async def test_update_lost_orders_and_cancel_lost_orders(self):
        exchange = object.__new__(LighterExchange)
        lost_orders = {
            "1": type("Order", (), {"client_order_id": "1"})(),
            "2": type("Order", (), {"client_order_id": "2"})(),
        }
        exchange._order_tracker = type("Tracker", (), {"lost_orders": lost_orders})()
        exchange._update_orders_with_error_handler = AsyncMock()
        exchange._request_order_status = AsyncMock()
        exchange._handle_update_error_for_lost_order = AsyncMock()
        exchange._execute_order_cancel = AsyncMock(return_value="")

        await exchange._update_lost_orders()
        await exchange._cancel_lost_orders()

        self.assertEqual(1, exchange._update_orders_with_error_handler.await_count)
        self.assertEqual(2, exchange._execute_order_cancel.await_count)

    async def test_execute_orders_cancel(self):
        exchange = object.__new__(LighterExchange)
        exchange.current_timestamp = 1700000000
        exchange._execute_order_cancel = AsyncMock(side_effect=["HBOT-6", ""])

        orders = [
            type("Order", (), {"client_order_id": "HBOT-6", "trading_pair": "ETH-USDC"})(),
            type("Order", (), {"client_order_id": "HBOT-7", "trading_pair": "ETH-USDC"})(),
        ]

        updates = await exchange._execute_orders_cancel(orders)
        self.assertEqual(1, len(updates))
        self.assertEqual("HBOT-6", updates[0].client_order_id)
        self.assertEqual(OrderState.CANCELED, updates[0].new_state)

    async def test_request_order_fills_by_exchange_order_id_filters(self):
        exchange = object.__new__(LighterExchange)
        order = type("Order", (), {"exchange_order_id": "42"})()
        exchange._request_order_fills_from_trades_api = AsyncMock(
            return_value=[
                {"order_id": 1, "trade_id": "a"},
                {"order_id": 42, "trade_id": "b"},
                {"order_id": 42, "trade_id": "c"},
            ]
        )

        fills = await exchange._request_order_fills_by_exchange_order_id(order)

        self.assertEqual(2, len(fills))
        self.assertEqual(["b", "c"], [f["trade_id"] for f in fills])

    def test_state_from_raw_order_status(self):
        exchange = object.__new__(LighterExchange)

        self.assertEqual(OrderState.CANCELED, exchange._state_from_raw_order_status("canceled"))
        self.assertEqual(OrderState.PARTIALLY_FILLED, exchange._state_from_raw_order_status("partially_filled"))
        self.assertEqual(OrderState.OPEN, exchange._state_from_raw_order_status("unknown"))
