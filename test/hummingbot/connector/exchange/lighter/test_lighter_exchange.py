import sys
import types
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock

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

    def test_account_from_response_variants(self):
        self.assertEqual({"assets": []}, LighterExchange._account_from_response({"data": {"assets": []}}))
        self.assertEqual({"assets": [1]}, LighterExchange._account_from_response({"data": [{"assets": [1]}]}))
        self.assertEqual({"assets": [2]}, LighterExchange._account_from_response({"accounts": [{"assets": [2]}]}))

    def test_is_ok_response(self):
        self.assertTrue(LighterExchange._is_ok_response({"success": True}))
        self.assertTrue(LighterExchange._is_ok_response({"code": 200}))
        self.assertFalse(LighterExchange._is_ok_response({"code": 500}))

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
