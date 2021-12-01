import unittest
from decimal import Decimal
from hummingbot.core.event.events import TradeType
from hummingbot.strategy.triangular_arbitrage.order_tracking.order_state import OrderState
from hummingbot.strategy.triangular_arbitrage.order_tracking.order import Order


class TriangularArbitrageOrderTest(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.trading_pair = "BTC-USDT"

    def test_order_create(self):
        order = Order(self.trading_pair, "order-id", Decimal("100."), Decimal("10."), TradeType.BUY)
        self.assertEqual(order.id, "order-id")
        self.assertTrue(order.state, OrderState.UNSENT)
        self.assertTrue(order.side, TradeType.BUY)
        self.assertFalse(order.is_live_uncancelled())
        self.assertFalse(order.is_live())
        self.assertEqual(order.total, Decimal("100.") * Decimal("10."))

    def test_order_active(self):
        order = Order(self.trading_pair, None, Decimal("100."), Decimal("10."), TradeType.BUY)
        order.mark_active()
        self.assertTrue(order.state, OrderState.ACTIVE)
        self.assertTrue(order.is_live_uncancelled())
        self.assertTrue(order.is_live())
        self.assertTrue(order.time_activated > order.time_conceived)

    def test_order_cancel(self):
        order = Order(self.trading_pair, None, Decimal("100."), Decimal("10."), TradeType.BUY)
        order.mark_active()
        order.mark_canceled()
        self.assertFalse(order.is_live_uncancelled())
        self.assertTrue(order.last_cancelled > order.time_conceived)
        self.assertTrue(order.last_cancelled > order.time_activated)
        self.assertTrue(order.is_live())
