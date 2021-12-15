from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.binance.binance_in_flight_order import BinanceInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class BinanceInFlightOrderTests(TestCase):

    def setUp(self):
        super().setUp()
        self.base_token = "BTC"
        self.quote_token = "USDT"
        self.trading_pair = f"{self.base_token}-{self.quote_token}"

    def test_creation_from_json(self):
        order_info = {
            "client_order_id": "OID1",
            "exchange_order_id": "EOID1",
            "trading_pair": self.trading_pair,
            "order_type": OrderType.LIMIT.name,
            "trade_type": TradeType.BUY.name,
            "price": "1000",
            "amount": "1",
            "executed_amount_base": "0.5",
            "executed_amount_quote": "500",
            "fee_asset": "USDT",
            "fee_paid": "5",
            "last_state": "closed",
        }

        order = BinanceInFlightOrder.from_json(order_info)

        self.assertEqual(order_info["client_order_id"], order.client_order_id)
        self.assertEqual(order_info["exchange_order_id"], order.exchange_order_id)
        self.assertEqual(order_info["trading_pair"], order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.BUY, order.trade_type)
        self.assertEqual(Decimal(order_info["price"]), order.price)
        self.assertEqual(Decimal(order_info["amount"]), order.amount)
        self.assertEqual(order_info["last_state"], order.last_state)
        self.assertEqual(Decimal(order_info["executed_amount_base"]), order.executed_amount_base)
        self.assertEqual(Decimal(order_info["executed_amount_quote"]), order.executed_amount_quote)
        self.assertEqual(Decimal(order_info["fee_paid"]), order.fee_paid)
        self.assertEqual(order_info["fee_asset"], order.fee_asset)
        self.assertEqual(order_info, order.to_json())

    def test_id_done_state(self):
        not_done_states = ["NEW", "PENDING_CANCEL"]
        done_states = ["FILLED", "CANCELED", "REJECTED", "EXPIRED"]

        order = BinanceInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1))

        for state in not_done_states:
            order.last_state = state
            self.assertFalse(order.is_done, f"The state {state} should not be final")
        for state in done_states:
            order.last_state = state
            self.assertTrue(order.is_done, f"The state {state} should be final")

    def test_id_failure_state(self):
        not_failure_states = ["NEW", "PENDING_CANCEL", "FILLED", "CANCELED"]
        failure_states = ["REJECTED", "EXPIRED"]

        order = BinanceInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1))

        for state in not_failure_states:
            order.last_state = state
            self.assertFalse(order.is_failure, f"The state {state} should not be failure")
        for state in failure_states:
            order.last_state = state
            self.assertTrue(order.is_failure, f"The state {state} should be failure")

    def test_id_cancelled_state(self):
        not_cancelled_states = ["NEW", "PENDING_CANCEL", "FILLED", "REJECTED", "EXPIRED"]
        cancelled_states = ["CANCELED"]

        order = BinanceInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1))

        for state in not_cancelled_states:
            order.last_state = state
            self.assertFalse(order.is_cancelled, f"The state {state} should not be cancelled")
        for state in cancelled_states:
            order.last_state = state
            self.assertTrue(order.is_cancelled, f"The state {state} should be cancelled")
