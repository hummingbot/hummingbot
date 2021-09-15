from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.kraken.kraken_in_flight_order import KrakenInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class KrakenInFlightOrderTests(TestCase):
    def test_order_is_local_after_creation(self):
        order = KrakenInFlightOrder(
            client_order_id="someId",
            exchange_order_id=None,
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(45000),
            amount=Decimal(1),
            userref=1,
        )

        self.assertTrue(order.is_local)
