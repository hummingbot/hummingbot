from decimal import Decimal
from unittest import TestCase

from hummingbot.core.data_type.common import OrderType, PositionSide, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder
from hummingbot.smart_components.position_executor.data_types import (
    PositionConfig,
    PositionExecutorStatus,
    TrackedOrder,
)


class TestPositionExecutorDataTypes(TestCase):
    def test_position_config_model(self):
        config = PositionConfig(timestamp=1234567890, trading_pair="ETH-USDT", exchange="binance",
                                order_type=OrderType.LIMIT,
                                side=PositionSide.LONG, entry_price=Decimal("100"), amount=Decimal("1"),
                                stop_loss=Decimal("0.05"), take_profit=Decimal("0.1"), time_limit=60)
        self.assertEqual(config.trading_pair, "ETH-USDT")
        self.assertEqual(config.exchange, "binance")
        self.assertEqual(config.order_type, OrderType.LIMIT)
        self.assertEqual(config.side, PositionSide.LONG)
        self.assertEqual(config.entry_price, Decimal("100"))
        self.assertEqual(config.amount, Decimal("1"))
        self.assertEqual(config.stop_loss, Decimal("0.05"))
        self.assertEqual(config.take_profit, Decimal("0.1"))
        self.assertEqual(config.time_limit, 60)

    def test_position_executor_status_enum(self):
        self.assertEqual(PositionExecutorStatus.NOT_STARTED.name, "NOT_STARTED")
        self.assertEqual(PositionExecutorStatus.NOT_STARTED.value, 1)
        self.assertEqual(PositionExecutorStatus.ORDER_PLACED.name, "ORDER_PLACED")
        self.assertEqual(PositionExecutorStatus.ORDER_PLACED.value, 2)
        self.assertEqual(PositionExecutorStatus.CANCELED_BY_TIME_LIMIT.name, "CANCELED_BY_TIME_LIMIT")
        self.assertEqual(PositionExecutorStatus.CANCELED_BY_TIME_LIMIT.value, 3)
        self.assertEqual(PositionExecutorStatus.ACTIVE_POSITION.name, "ACTIVE_POSITION")
        self.assertEqual(PositionExecutorStatus.ACTIVE_POSITION.value, 4)
        self.assertEqual(PositionExecutorStatus.CLOSE_PLACED.name, "CLOSE_PLACED")
        self.assertEqual(PositionExecutorStatus.CLOSE_PLACED.value, 5)
        self.assertEqual(PositionExecutorStatus.CLOSED_BY_TIME_LIMIT.name, "CLOSED_BY_TIME_LIMIT")
        self.assertEqual(PositionExecutorStatus.CLOSED_BY_TIME_LIMIT.value, 6)
        self.assertEqual(PositionExecutorStatus.CLOSED_BY_STOP_LOSS.name, "CLOSED_BY_STOP_LOSS")
        self.assertEqual(PositionExecutorStatus.CLOSED_BY_STOP_LOSS.value, 7)
        self.assertEqual(PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT.name, "CLOSED_BY_TAKE_PROFIT")
        self.assertEqual(PositionExecutorStatus.CLOSED_BY_TAKE_PROFIT.value, 8)

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
