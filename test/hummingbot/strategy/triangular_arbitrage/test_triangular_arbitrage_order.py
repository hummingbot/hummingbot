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

    def test_order_mark_canceled(self):
        order = Order(self.trading_pair, None, Decimal("100."), Decimal("10."), TradeType.BUY)
        order.mark_active()
        order.mark_canceled()
        self.assertFalse(order.is_live_uncancelled())
        self.assertTrue(order.last_cancelled > order.time_conceived)
        self.assertTrue(order.last_cancelled > order.time_activated)
        self.assertTrue(order.is_live())

    def test_order_is_live_uncancelled(self):
        order = Order(self.trading_pair, None, Decimal("100."), Decimal("10."), TradeType.BUY, OrderState.ACTIVE)
        self.assertTrue(order.is_live_uncancelled())
        order = Order(self.trading_pair, None, Decimal("100."), Decimal("10."), TradeType.BUY, OrderState.CANCELED)
        self.assertFalse(order.is_live_uncancelled())

    def test_order_total(self):
        order = Order(self.trading_pair, None, Decimal("100."), Decimal("10."), TradeType.BUY, OrderState.ACTIVE)
        self.assertEqual(order.total, Decimal('1000'))

    def test_update_order_id(self):
        order = Order(self.trading_pair, None, Decimal("100."), Decimal("10."), TradeType.BUY, OrderState.ACTIVE)
        order.update_order_id("5")
        self.assertEqual(order.id, "5")