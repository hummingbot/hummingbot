import sys
import types
import unittest
from decimal import Decimal
from enum import Enum
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock

from hummingbot.core.data_type.common import TradeType
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
