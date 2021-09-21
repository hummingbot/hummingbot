from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.bitmart.bitmart_in_flight_order import BitmartInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class BitmartInFlightOrderTests(TestCase):

    def _example_json(self):
        return {"client_order_id": "C1",
                "exchange_order_id": "1",
                "trading_pair": "BTC-USDT",
                "order_type": "LIMIT",
                "trade_type": "BUY",
                "price": "35000",
                "amount": "1.1",
                "last_state": "OPEN",
                "executed_amount_base": "0.5",
                "executed_amount_quote": "15000",
                "fee_asset": "BTC",
                "fee_paid": "0"}

    def test_instance_creation(self):
        order = BitmartInFlightOrder(client_order_id="C1",
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
        self.assertEqual(Decimal("0"), order.fee_paid)
        self.assertEqual("OPEN", order.last_state)

    def test_create_from_json(self):
        order = BitmartInFlightOrder.from_json(self._example_json())

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
        self.assertEqual("OPEN", order.last_state)

    def test_is_done(self):
        order = BitmartInFlightOrder.from_json(self._example_json())

        self.assertFalse(order.is_done)

        for status in ["FILLED", "CANCELED", "REJECTED", "EXPIRED", "FAILED"]:
            order.last_state = status
            self.assertTrue(order.is_done)

    def test_is_failure(self):
        order = BitmartInFlightOrder.from_json(self._example_json())

        for status in ["FILLED", "CANCELED", "ACTIVE", "EXPIRED", "OPEN"]:
            order.last_state = status
            self.assertFalse(order.is_failure)

        for status in ["REJECTED", "FAILED"]:
            order.last_state = status
            self.assertTrue(order.is_failure)

    def test_is_cancelled(self):
        order = BitmartInFlightOrder.from_json(self._example_json())

        for status in ["ACTIVE", "FILLED", "REJECTED", "FAILED"]:
            order.last_state = status
            self.assertFalse(order.is_cancelled)

        for status in ["CANCELED", "EXPIRED"]:
            order.last_state = status
            self.assertTrue(order.is_cancelled)

    def test_to_json(self):
        order = BitmartInFlightOrder.from_json(self._example_json())

        self.assertEqual(self._example_json(), order.to_json())

    def test_update_with_trade_update_rest_and_ws(self):
        order = BitmartInFlightOrder.from_json(self._example_json())

        trade_update_from_ws = {
            "symbol": "BTC_USDT",
            "side": "buy",
            "type": "limit",
            "notional": "0.00000000",
            "size": "1.10000",
            "ms_t": "1609926028000",
            "price": "35000.00",
            "filled_notional": "21000.00",
            "filled_size": "0.70000",
            "margin_trading": "0",
            "state": "5",
            "order_id": "1",
            "order_type": "0",
            "last_fill_time": 125,
            "last_fill_price": "30000.00",
            "last_fill_count": "0.20000"
        }

        (delta_trade_amount, delta_trade_price, trade_id) = order.update_with_order_update_ws(trade_update_from_ws)
        self.assertNotEqual("", trade_id)
        self.assertEqual(Decimal("0.20000") + Decimal(self._example_json()["executed_amount_base"]),
                         order.executed_amount_base)
        self.assertEqual(Decimal("21000.00"), order.executed_amount_quote)

        repeated_trade_update_from_rest = {
            "order_id": "1",
            "symbol": "BTC_USDT",
            "create_time": 123,
            "side": "buy",
            "type": "limit",
            "price": "35000.00",
            "price_avg": "35000.00",
            "size": "1.10000",
            "notional": "0.00000000",
            "filled_notional": "10500.00",
            "filled_size": "0.30000",
            "status": "5"
        }

        (delta_trade_amount, delta_trade_price, trade_id) = order.update_with_trade_update_rest(repeated_trade_update_from_rest)
        self.assertEqual("", trade_id)
