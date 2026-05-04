import asyncio
import sys
import types
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

try:
    __import__("hummingbot.core.data_type.limit_order")
except Exception:
    if "hummingbot.core.data_type.limit_order" not in sys.modules:
        fake_limit_order = types.ModuleType("hummingbot.core.data_type.limit_order")

        class LimitOrder:
            pass

        fake_limit_order.LimitOrder = LimitOrder
        sys.modules["hummingbot.core.data_type.limit_order"] = fake_limit_order

try:
    __import__("hummingbot.core.data_type.order_book")
except Exception:
    if "hummingbot.core.data_type.order_book" not in sys.modules:
        fake_order_book = types.ModuleType("hummingbot.core.data_type.order_book")

        class OrderBook:
            def apply_snapshot(self, bids, asks, update_id):
                _ = bids
                _ = asks
                _ = update_id

        fake_order_book.OrderBook = OrderBook
        sys.modules["hummingbot.core.data_type.order_book"] = fake_order_book

try:
    from hummingbot.connector.exchange.lighter.lighter_exchange import LighterExchange
    _LIGHTER_EXCHANGE_AVAILABLE = True
except ModuleNotFoundError:
    _LIGHTER_EXCHANGE_AVAILABLE = False


@unittest.skipUnless(_LIGHTER_EXCHANGE_AVAILABLE, "Core exchange runtime modules are unavailable in this local environment")
class LighterExchangeUserStreamPayloadTests(IsolatedAsyncioWrapperTestCase):
    def test_extract_private_stream_payloads_from_account_all(self):
        event = {
            "type": "update/account_all",
            "channel": "account_all:123",
            "data": {
                "assets": [{"symbol": "USDC", "balance": "10", "locked_balance": "2"}],
                "trades": [{"trade_id": "t1"}],
                "orders": [{"order_id": "o1"}],
            },
        }

        account_data, trades, orders = LighterExchange._extract_private_stream_payloads(event)

        self.assertIsNotNone(account_data)
        self.assertEqual(1, len(trades))
        self.assertEqual(1, len(orders))

    def test_extract_private_stream_payloads_from_dedicated_channels(self):
        order_event = {
            "type": "update/account_order_updates",
            "channel": "account_order_updates:123",
            "data": {"order_id": "o1", "order_status": "open"},
        }
        trade_event = {
            "type": "update/account_trades",
            "channel": "account_trades:123",
            "data": [{"trade_id": "t1", "price": "1.1", "size": "2"}],
        }

        account_data_1, trades_1, orders_1 = LighterExchange._extract_private_stream_payloads(order_event)
        account_data_2, trades_2, orders_2 = LighterExchange._extract_private_stream_payloads(trade_event)

        self.assertIsNone(account_data_1)
        self.assertEqual(0, len(trades_1))
        self.assertEqual(1, len(orders_1))

        self.assertIsNone(account_data_2)
        self.assertEqual(1, len(trades_2))
        self.assertEqual(0, len(orders_2))

    def test_extract_private_stream_payloads_from_account_all_orders_data_payload(self):
        dict_event = {
            "type": "update/account_all_orders",
            "channel": "account_all_orders:123",
            "data": {"order_id": "o1", "order_status": "filled"},
        }
        list_event = {
            "type": "update/account_all_orders",
            "channel": "account_all_orders:123",
            "data": [
                {"order_id": "o2", "order_status": "open"},
                {"order_id": "o3", "order_status": "canceled"},
            ],
        }

        _, _, dict_orders = LighterExchange._extract_private_stream_payloads(dict_event)
        _, _, list_orders = LighterExchange._extract_private_stream_payloads(list_event)

        self.assertEqual([{"order_id": "o1", "order_status": "filled"}], dict_orders)
        self.assertEqual(2, len(list_orders))

    def test_extract_private_stream_payloads_from_account_all_assets(self):
        event = {
            "type": "update/account_all_assets",
            "channel": "account_all_assets:123",
            "assets": {
                "3": {"symbol": "USDC", "balance": "100", "locked_balance": "12"},
                "1": {"symbol": "LINK", "balance": "4", "locked_balance": "1"},
            },
        }

        account_data, trades, orders = LighterExchange._extract_private_stream_payloads(event)

        self.assertIsNotNone(account_data)
        self.assertEqual(2, len(account_data["assets"]))
        self.assertEqual(0, len(trades))
        self.assertEqual(0, len(orders))

    def test_extract_private_stream_payloads_from_singular_trade_and_order_fields(self):
        event = {
            "type": "update/account_all",
            "channel": "account_all:123",
            "data": {
                "trade": {"trade_id": "t1", "price": "1.1", "size": "2"},
                "order": {"order_id": "o1", "order_status": "open"},
            },
        }

        account_data, trades, orders = LighterExchange._extract_private_stream_payloads(event)

        self.assertIsNotNone(account_data)
        self.assertEqual(1, len(trades))
        self.assertEqual(1, len(orders))

    async def test_user_stream_event_listener_triggers_balance_refresh_without_assets(self):
        exchange = LighterExchange.__new__(LighterExchange)
        exchange._process_balance_message_from_account = lambda _: None
        exchange._trade_update_from_raw_message = lambda _: None
        exchange._order_update_from_raw_message = lambda _: None
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_trade_update": lambda self, _: None,
                "process_order_update": lambda self, _: None,
            },
        )()
        exchange._safe_update_balances_from_private_stream = AsyncMock()
        exchange._current_timestamp_safely = lambda: 1000.0
        exchange._last_private_stream_balance_sync_ts = 0.0
        exchange._sleep = AsyncMock()

        async def events():
            yield {
                "type": "update/account_all",
                "channel": "account_all:123",
                "data": {
                    "orders": [{"order_id": "o1", "order_status": "open"}],
                    "trades": [{"trade_id": "t1", "price": "1.1", "size": "2"}],
                },
            }
            raise asyncio.CancelledError

        exchange._iter_user_event_queue = events

        with self.assertRaises(asyncio.CancelledError):
            await exchange._user_stream_event_listener()

        self.assertEqual(1000.0, exchange._last_private_stream_balance_sync_ts)

    async def test_user_stream_event_listener_processes_dedicated_payloads(self):
        exchange = LighterExchange.__new__(LighterExchange)
        captured = {
            "balances": 0,
            "trades": 0,
            "orders": 0,
        }

        _mock_trade_update = MagicMock()
        _mock_trade_update.client_order_id = "HBOT-TEST"
        _mock_trade_update.exchange_order_id = "1"
        exchange._process_balance_message_from_account = lambda _: captured.__setitem__("balances", captured["balances"] + 1)
        exchange._trade_update_from_raw_message = lambda _: _mock_trade_update
        exchange._order_update_from_raw_message = lambda _: MagicMock(new_state=None, client_order_id="HBOT-TEST", exchange_order_id="1")
        exchange._order_tracker = type(
            "Tracker",
            (),
            {
                "process_trade_update": lambda self, _: captured.__setitem__("trades", captured["trades"] + 1),
                "process_order_update": lambda self, _: captured.__setitem__("orders", captured["orders"] + 1),
                "all_fillable_orders": {},
                "all_updatable_orders": {},
                "all_fillable_orders_by_exchange_order_id": {},
            },
        )()
        exchange._sleep = AsyncMock()

        async def events():
            yield {
                "type": "update/account_info",
                "channel": "account_info:123",
                "data": {"assets": [{"symbol": "USDC", "balance": "10", "locked_balance": "1"}]},
            }
            yield {
                "type": "update/account_trades",
                "channel": "account_trades:123",
                "data": [{"trade_id": "t1", "price": "1.1", "size": "2"}],
            }
            yield {
                "type": "update/account_order_updates",
                "channel": "account_order_updates:123",
                "data": {"order_id": "o1", "order_status": "open"},
            }
            raise asyncio.CancelledError

        exchange._iter_user_event_queue = events

        with self.assertRaises(asyncio.CancelledError):
            await exchange._user_stream_event_listener()

        self.assertEqual(1, captured["balances"])
        self.assertEqual(1, captured["trades"])
        self.assertEqual(1, captured["orders"])
