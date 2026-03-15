from decimal import Decimal
from unittest import TestCase

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.strategy_v2.models.executors import CloseType, TrackedOrder


class TestPositionExecutorDataTypes(TestCase):

    def test_position_executor_close_types_enum(self):
        self.assertEqual(CloseType.TIME_LIMIT.name, "TIME_LIMIT")
        self.assertEqual(CloseType.TIME_LIMIT.value, 1)
        self.assertEqual(CloseType.STOP_LOSS.name, "STOP_LOSS")
        self.assertEqual(CloseType.STOP_LOSS.value, 2)
        self.assertEqual(CloseType.TAKE_PROFIT.name, "TAKE_PROFIT")
        self.assertEqual(CloseType.TAKE_PROFIT.value, 3)
        self.assertEqual(CloseType.EXPIRED.name, "EXPIRED")
        self.assertEqual(CloseType.EXPIRED.value, 4)
        self.assertEqual(CloseType.EARLY_STOP.name, "EARLY_STOP")
        self.assertEqual(CloseType.EARLY_STOP.value, 5)

    def test_tracked_order(self):
        order = TrackedOrder()
        self.assertIsNone(order.order_id)
        self.assertIsNone(order.order)

    def test_tracked_order_order_id(self):
        order = TrackedOrder()
        order.order_id = "12345"
        self.assertEqual(order.order_id, "12345")

    def test_tracked_order_order(self):
        in_flight_order = InFlightOrder(
            client_order_id="12345",
            trading_pair="ETH/USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            creation_timestamp=12341451532,
            price=Decimal("1"))
        order = TrackedOrder()
        order.order = in_flight_order
        self.assertEqual(order.order, in_flight_order)
