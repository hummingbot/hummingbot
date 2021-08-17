from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.ndax.ndax_in_flight_order import \
    NdaxInFlightOrder, WORKING_LOCAL_STATUS
from hummingbot.core.event.events import OrderType, TradeType


class NdaxInFlightOrderTests(TestCase):

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
        order = NdaxInFlightOrder(client_order_id="C1",
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
        self.assertEqual(WORKING_LOCAL_STATUS, order.last_state)

    def test_create_from_json(self):
        order = NdaxInFlightOrder.from_json(self._example_json())

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
        order = NdaxInFlightOrder.from_json(self._example_json())

        self.assertFalse(order.is_done)

        for status in ["FullyExecuted", "Canceled", "Rejected", "Expired"]:
            order.last_state = status
            self.assertTrue(order.is_done)

    def test_is_failure(self):
        order = NdaxInFlightOrder.from_json(self._example_json())

        for status in ["Working", "FullyExecuted", "Canceled", "Expired"]:
            order.last_state = status
            self.assertFalse(order.is_failure)

        order.last_state = "Rejected"
        self.assertTrue(order.is_failure)

    def test_is_cancelled(self):
        order = NdaxInFlightOrder.from_json(self._example_json())

        for status in ["Working", "FullyExecuted", "Rejected"]:
            order.last_state = status
            self.assertFalse(order.is_cancelled)

        for status in ["Canceled", "Expired"]:
            order.last_state = status
            self.assertTrue(order.is_cancelled)

    def test_mark_as_filled(self):
        order = NdaxInFlightOrder.from_json(self._example_json())

        order.mark_as_filled()
        self.assertEqual("FullyExecuted", order.last_state)

    def test_to_json(self):
        order = NdaxInFlightOrder.from_json(self._example_json())

        self.assertEqual(self._example_json(), order.to_json())

    def test_update_with_trade_update(self):
        order = NdaxInFlightOrder.from_json(self._example_json())

        trade_update_for_different_order_id = {
            "OMSId": 1,
            "TradeId": 213,
            "OrderId": 5,
            "AccountId": 4,
            "ClientOrderId": 0,
            "InstrumentId": 1,
            "Side": "Buy",
            "Quantity": 0.01,
            "Price": 95,
            "Value": 0.95,
            "TradeTime": 635978008210426109,
            "ContraAcctId": 3,
            "OrderTradeRevision": 1,
            "Direction": "NoChange"
        }

        update_result = order.update_with_trade_update(trade_update_for_different_order_id)
        self.assertFalse(update_result)

        valid_trade_update = {
            "OMSId": 1,
            "TradeId": 213,
            "OrderId": 1,
            "AccountId": 4,
            "ClientOrderId": 0,
            "InstrumentId": 1,
            "Side": "Buy",
            "Quantity": 0.1,
            "Price": 35000,
            "Value": 3500,
            "TradeTime": 635978008210426109,
            "ContraAcctId": 3,
            "OrderTradeRevision": 1,
            "Direction": "NoChange"
        }

        update_result = order.update_with_trade_update(valid_trade_update)
        self.assertTrue(update_result)
        self.assertEqual(Decimal("0.1") + Decimal(self._example_json()["executed_amount_base"]),
                         order.executed_amount_base)
        self.assertEqual(Decimal("3500") + Decimal(self._example_json()["executed_amount_quote"]),
                         order.executed_amount_quote)

        repeated_trade_update = valid_trade_update
        update_result = order.update_with_trade_update(repeated_trade_update)
        self.assertFalse(update_result)
