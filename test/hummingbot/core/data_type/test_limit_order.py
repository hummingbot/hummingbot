import unittest
from decimal import Decimal
import time
from hummingbot.core.data_type.limit_order import LimitOrder
from hummingbot.core.event.events import LimitOrderStatus


class LimitOrderUnitTest(unittest.TestCase):
    def test_order_creation_with_default_values(self):
        order = LimitOrder(client_order_id="HBOT_1",
                           trading_pair="HBOT-USDT",
                           is_buy=False,
                           base_currency="HBOT",
                           quote_currency="USDT",
                           price=Decimal("100"),
                           quantity=Decimal("1.5")
                           )
        self.assertEqual(order.client_order_id, "HBOT_1")
        self.assertEqual(order.trading_pair, "HBOT-USDT")
        self.assertEqual(order.is_buy, False)
        self.assertEqual(order.base_currency, "HBOT")
        self.assertEqual(order.quote_currency, "USDT")
        self.assertEqual(order.price, Decimal("100"))
        self.assertEqual(order.quantity, Decimal("1.5"))
        self.assertTrue(Decimal.is_nan(order.filled_quantity))
        self.assertEqual(order.creation_timestamp, 0)
        self.assertEqual(order.status, LimitOrderStatus.UNKNOWN)
        self.assertEqual(-1, order.age_seconds())

    def test_order_creation_with_all_values(self):
        created = int((time.time() - 10.) * 1000000)
        order = LimitOrder(client_order_id="HBOT_1",
                           trading_pair="HBOT-USDT",
                           is_buy=False,
                           base_currency="HBOT",
                           quote_currency="USDT",
                           price=Decimal("100"),
                           quantity=Decimal("1.5"),
                           filled_quantity=Decimal("0.5"),
                           creation_timestamp=created,
                           status=LimitOrderStatus.OPEN
                           )
        self.assertEqual(order.filled_quantity, Decimal("0.5"))
        self.assertEqual(order.creation_timestamp, created)
        self.assertEqual(order.status, LimitOrderStatus.OPEN)
        self.assertEqual(order.age_seconds(), 10)
