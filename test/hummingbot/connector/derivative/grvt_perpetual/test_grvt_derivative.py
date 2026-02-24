import asyncio
import importlib
import sys
import types
import unittest
from decimal import Decimal
from inspect import isabstract
from types import SimpleNamespace
from unittest.mock import AsyncMock


def _install_cython_fallback_stubs():
    def _order_book_module():
        module = types.ModuleType("hummingbot.core.data_type.order_book")

        class OrderBook:
            def apply_snapshot(self, bids, asks, update_id):
                pass

        module.OrderBook = OrderBook
        return module

    def _limit_order_module():
        module = types.ModuleType("hummingbot.core.data_type.limit_order")

        class LimitOrder:
            pass

        module.LimitOrder = LimitOrder
        return module

    def _exchange_base_module():
        module = types.ModuleType("hummingbot.connector.exchange_base")

        class ExchangeBase:
            def __init__(self, *args, **kwargs):
                pass

        module.ExchangeBase = ExchangeBase
        return module

    def _trading_rule_module():
        module = types.ModuleType("hummingbot.connector.trading_rule")

        class TradingRule:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        module.TradingRule = TradingRule
        return module

    def _network_iterator_module():
        module = types.ModuleType("hummingbot.core.network_iterator")

        class NetworkStatus:
            NOT_CONNECTED = 0
            CONNECTED = 1

        module.NetworkStatus = NetworkStatus
        return module

    module_factories = {
        "hummingbot.core.data_type.order_book": _order_book_module,
        "hummingbot.core.data_type.limit_order": _limit_order_module,
        "hummingbot.connector.exchange_base": _exchange_base_module,
        "hummingbot.connector.trading_rule": _trading_rule_module,
        "hummingbot.core.network_iterator": _network_iterator_module,
    }
    for module_name, factory in module_factories.items():
        if module_name in sys.modules:
            continue
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError:
            sys.modules[module_name] = factory()


_install_cython_fallback_stubs()

from hummingbot.connector.derivative.grvt_perpetual.grvt_derivative import GrvtDerivative
from hummingbot.core.data_type.common import OrderType, PositionAction, TradeType


class GrvtDerivativeTests(unittest.TestCase):
    def test_class_declared(self):
        self.assertEqual("GrvtDerivative", GrvtDerivative.__name__)

    def test_class_is_concrete(self):
        self.assertFalse(isabstract(GrvtDerivative))

    def test_place_order_timeout_does_not_loop_forever(self):
        connector = self._mock_connector()
        call_counter = {"count": 0}

        async def timeout_post(*args, **kwargs):
            call_counter["count"] += 1
            raise asyncio.TimeoutError()

        connector._api_post = AsyncMock(side_effect=timeout_post)
        with self.assertRaises(asyncio.TimeoutError):
            asyncio.run(
                asyncio.wait_for(
                    GrvtDerivative._place_order(
                        connector,
                        order_id="cid-timeout",
                        trading_pair="BTC-USDC",
                        amount=Decimal("1"),
                        trade_type=TradeType.BUY,
                        order_type=OrderType.LIMIT,
                        price=Decimal("100"),
                        position_action=PositionAction.OPEN,
                    ),
                    timeout=0.2,
                )
            )
        self.assertEqual(1, call_counter["count"])

    def test_place_order_quantizes_amount_and_price(self):
        connector = self._mock_connector()
        captured_request = {}

        async def ok_post(*args, **kwargs):
            captured_request.update(kwargs)
            return {"data": {"orderId": "ex-123", "timestamp": 1700000000123}}

        connector._api_post = AsyncMock(side_effect=ok_post)

        exchange_order_id, timestamp = asyncio.run(
            GrvtDerivative._place_order(
                connector,
                order_id="cid-1",
                trading_pair="BTC-USDC",
                amount=Decimal("1.239"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("123.78"),
                position_action=PositionAction.OPEN,
            )
        )

        self.assertEqual("ex-123", exchange_order_id)
        self.assertAlmostEqual(1700000000.123, timestamp)
        payload = captured_request["data"]
        self.assertEqual(Decimal("1.23"), Decimal(payload["size"]))
        self.assertEqual(Decimal("123.5"), Decimal(payload["price"]))

    def test_market_order_payload_omits_price(self):
        connector = self._mock_connector()
        captured_request = {}

        async def ok_post(*args, **kwargs):
            captured_request.update(kwargs)
            return {"data": {"orderId": "ex-456", "timestamp": 1700000000999}}

        connector._api_post = AsyncMock(side_effect=ok_post)

        asyncio.run(
            GrvtDerivative._place_order(
                connector,
                order_id="cid-2",
                trading_pair="BTC-USDC",
                amount=Decimal("2.003"),
                trade_type=TradeType.SELL,
                order_type=OrderType.MARKET,
                price=Decimal("200.19"),
                position_action=PositionAction.CLOSE,
            )
        )

        payload = captured_request["data"]
        self.assertEqual(Decimal("2.00"), Decimal(payload["size"]))
        self.assertNotIn("price", payload)
        self.assertEqual("ioc", payload["timeInForce"])

    def _mock_connector(self):
        connector = SimpleNamespace()
        connector.current_timestamp = 1700000000.0
        connector._time = lambda: 1700000000.0
        connector._trading_rules = {
            "BTC-USDC": SimpleNamespace(
                min_base_amount_increment=Decimal("0.01"),
                min_price_increment=Decimal("0.5"),
                min_order_size=Decimal("0.01"),
            )
        }
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value="BTC-USDC")
        connector._extract_error_message = lambda payload: None
        connector._extract_order_payload = lambda payload, client_order_id=None, exchange_order_id=None: payload.get("data", {})
        connector._extract_timestamp = GrvtDerivative._extract_timestamp.__get__(connector, SimpleNamespace)
        connector._quantize_size_for_api = GrvtDerivative._quantize_size_for_api.__get__(connector, SimpleNamespace)
        connector._quantize_price_for_api = GrvtDerivative._quantize_price_for_api.__get__(connector, SimpleNamespace)
        connector._truncate_to_step = GrvtDerivative._truncate_to_step.__get__(connector, SimpleNamespace)
        return connector
