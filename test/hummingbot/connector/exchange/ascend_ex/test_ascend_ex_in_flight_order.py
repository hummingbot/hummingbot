from decimal import Decimal
from unittest import TestCase

from hummingbot.core.event.events import OrderType, TradeType

from hummingbot.connector.exchange.ascend_ex.ascend_ex_in_flight_order import AscendExInFlightOrder


class AscendExInFlightOrderTests(TestCase):

    def test_open_status(self):
        order = AscendExInFlightOrder(client_order_id="1",
                                      exchange_order_id="2",
                                      trading_pair="BTC-USDT",
                                      order_type=OrderType.LIMIT,
                                      trade_type=TradeType.BUY,
                                      price=Decimal("40000"),
                                      amount=Decimal("1"),
                                      initial_state="NewLocal")

        self.assertFalse(order.is_open)

        order.update_status("New")
        self.assertTrue(order.is_open)
        order.update_status("PendingNew")
        self.assertTrue(order.is_open)
        order.update_status("PartiallyFilled")
        self.assertTrue(order.is_open)

        order.update_status("Filled")
        self.assertFalse(order.is_open)
        order.update_status("Rejected")
        self.assertFalse(order.is_open)
        order.update_status("Canceled")
        self.assertFalse(order.is_open)

    def test_done_status(self):
        order = AscendExInFlightOrder(client_order_id="1",
                                      exchange_order_id="2",
                                      trading_pair="BTC-USDT",
                                      order_type=OrderType.LIMIT,
                                      trade_type=TradeType.BUY,
                                      price=Decimal("40000"),
                                      amount=Decimal("1"),
                                      initial_state="NewLocal")

        self.assertFalse(order.is_done)

        order.update_status("New")
        self.assertFalse(order.is_done)
        order.update_status("PendingNew")
        self.assertFalse(order.is_done)
        order.update_status("PartiallyFilled")
        self.assertFalse(order.is_done)

        order.update_status("Filled")
        self.assertTrue(order.is_done)
        order.update_status("Rejected")
        self.assertTrue(order.is_done)
        order.update_status("Canceled")
        self.assertTrue(order.is_done)
