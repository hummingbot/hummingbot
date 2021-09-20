from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.coinzoom.coinzoom_in_flight_order import CoinzoomInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class CoinzoomInFlightOrderTests(TestCase):

    def test_order_is_local_after_creation(self):
        order = CoinzoomInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(45000),
            amount=Decimal(1)
        )

        self.assertTrue(order.is_local)

    def test_order_state_is_new_after_update_exchange_order_id(self):
        order = CoinzoomInFlightOrder(
            client_order_id="OID1",
            exchange_order_id=None,
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(45000),
            amount=Decimal(1)
        )

        order.update_exchange_order_id("EOID1")

        self.assertEqual("EOID1", order.exchange_order_id)
        self.assertFalse(order.is_local)
        self.assertFalse(order.is_done)
        self.assertFalse(order.is_failure)
        self.assertFalse(order.is_cancelled)
