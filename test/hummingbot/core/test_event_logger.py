import unittest
from decimal import Decimal

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import OrderFilledEvent


class EventLoggerTest(unittest.TestCase):
    def test_order_filled_events_are_bounded(self):
        event_logger = EventLogger(order_filled_event_maxlen=3)

        for index in range(5):
            event_logger(
                OrderFilledEvent(
                    timestamp=index,
                    order_id=f"order-{index}",
                    trading_pair="BTC-USDT",
                    trade_type=TradeType.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal("100"),
                    amount=Decimal("1"),
                    trade_fee=AddedToCostTradeFee(),
                )
            )

        self.assertEqual(
            ["order-2", "order-3", "order-4"],
            [event.order_id for event in event_logger.event_log],
        )

    def test_rejects_non_positive_order_filled_event_limit(self):
        with self.assertRaises(ValueError):
            EventLogger(order_filled_event_maxlen=0)


if __name__ == "__main__":
    unittest.main()
