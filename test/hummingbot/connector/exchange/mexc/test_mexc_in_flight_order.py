from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.mexc.mexc_in_flight_order import \
    MexcInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class MexcInFlightOrderTests(TestCase):

    def _example_json(self):
        return {"client_order_id": "C1",
                "exchange_order_id": "1",
                "trading_pair": "BTC-USDT",
                "order_type": "LIMIT",
                "trade_type": "BUY",
                "price": "35000",
                "amount": "1.1",
                "last_state": "Working",
                "executed_amount_base": "0.5",
                "executed_amount_quote": "15000",
                "fee_asset": "BTC",
                "fee_paid": "0"}

    def test_instance_creation(self):
        order = MexcInFlightOrder(client_order_id="C1",
                                  exchange_order_id="1",
                                  trading_pair="BTC-USDT",
                                  order_type=OrderType.LIMIT,
                                  trade_type=TradeType.SELL,
                                  price=Decimal("35000"),
                                  amount=Decimal("1.1"))

        self.assertEqual("C1", order.client_order_id)
        self.assertEqual("1", order.exchange_order_id)
        self.assertEqual("BTC-USDT", order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.SELL, order.trade_type)
        self.assertEqual(Decimal("35000"), order.price)
        self.assertEqual(Decimal("1.1"), order.amount)
        self.assertEqual(Decimal("0"), order.executed_amount_base)
        self.assertEqual(Decimal("0"), order.executed_amount_quote)
        self.assertEqual(order.quote_asset, order.fee_asset)
        self.assertEqual(Decimal("0"), order.fee_paid)

    def test_create_from_json(self):
        order = MexcInFlightOrder.from_json(self._example_json())

        self.assertEqual("C1", order.client_order_id)
        self.assertEqual("1", order.exchange_order_id)
        self.assertEqual("BTC-USDT", order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.BUY, order.trade_type)
        self.assertEqual(Decimal("35000"), order.price)
        self.assertEqual(Decimal("1.1"), order.amount)
        self.assertEqual(Decimal("0.5"), order.executed_amount_base)
        self.assertEqual(Decimal("15000"), order.executed_amount_quote)
        self.assertEqual(order.base_asset, order.fee_asset)
        self.assertEqual(Decimal("0"), order.fee_paid)
        self.assertEqual("Working", order.last_state)

    def test_is_done(self):
        order = MexcInFlightOrder.from_json(self._example_json())

        self.assertFalse(order.is_done)

        for status in ["FILLED", "CANCELED", "PARTIALLY_CANCELED"]:
            order.last_state = status
            self.assertTrue(order.is_done)

    def test_is_failure(self):
        order = MexcInFlightOrder.from_json(self._example_json())

        for status in ["NEW", "PARTIALLY_FILLED"]:
            order.last_state = status
            self.assertFalse(order.is_failure)

        # order.last_state = "Rejected"
        # self.assertTrue(order.is_failure)

    def test_is_cancelled(self):
        order = MexcInFlightOrder.from_json(self._example_json())

        for status in ["Working", "FullyExecuted", "Rejected"]:
            order.last_state = status
            self.assertFalse(order.is_cancelled)

    def test_mark_as_filled(self):
        order = MexcInFlightOrder.from_json(self._example_json())

        order.mark_as_filled()
        self.assertEqual("FILLED", order.last_state)

    def test_to_json(self):
        order = MexcInFlightOrder.from_json(self._example_json())

        self.assertEqual(self._example_json(), order.to_json())
