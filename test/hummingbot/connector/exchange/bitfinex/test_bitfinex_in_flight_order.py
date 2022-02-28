from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.bitfinex import OrderStatus
from hummingbot.connector.exchange.bitfinex.bitfinex_in_flight_order import BitfinexInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class BitfinexInFlightOrderTests(TestCase):

    def setUp(self):
        super().setUp()
        self.base_token = "BTC"
        self.quote_token = "USDT"
        self.trading_pair = f"{self.base_token}-{self.quote_token}"

    def test_update_with_partial_trade_event(self):
        order = BitfinexInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "order_id": "EOID1",
            "trade_id": 1,
            "amount": 0.1,
            "price": 10050.0,
            "fee": 10.0,
            "fee_currency": "USDC",
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual(OrderStatus.PARTIALLY, order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["amount"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["amount"])) * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["fee_currency"], order.fee_asset)

    def test_update_with_full_fill_trade_event(self):
        order = BitfinexInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "order_id": "EOID1",
            "trade_id": 1,
            "amount": 0.1,
            "price": 10050.0,
            "fee": 10.0,
            "fee_currency": "USDC",
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual(OrderStatus.PARTIALLY, order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["amount"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["amount"])) * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["fee_currency"], order.fee_asset)

        complete_event_info = {
            "order_id": "EOID1",
            "trade_id": 2,
            "amount": 0.9,
            "price": 10060.0,
            "fee": 50.0,
            "fee_currency": "USDC",
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_open)
        self.assertTrue(order.is_done)
        self.assertEqual(OrderStatus.EXECUTED, order.last_state)
        self.assertEqual(order.amount, order.executed_amount_base)
        expected_executed_quote_amount += Decimal(str(complete_event_info["amount"])) * Decimal(
            str(complete_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]) + Decimal(complete_event_info["fee"]), order.fee_paid)
        self.assertEqual(complete_event_info["fee_currency"], order.fee_asset)

    def test_update_with_repeated_trade_id_is_ignored(self):
        order = BitfinexInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "order_id": "EOID1",
            "trade_id": 1,
            "amount": 0.1,
            "price": 10050.0,
            "fee": 10.0,
            "fee_currency": "USDC",
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual(OrderStatus.PARTIALLY, order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["amount"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["amount"])) * Decimal(str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["fee_currency"], order.fee_asset)

        complete_event_info = {
            "order_id": "EOID1",
            "trade_id": 1,
            "amount": 1,
            "price": 10060.0,
            "fee": 50.0,
            "fee_currency": "USDC",
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertFalse(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual(OrderStatus.PARTIALLY, order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["amount"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["amount"])) * Decimal(
            str(trade_event_info["price"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["fee"]), order.fee_paid)
        self.assertEqual(trade_event_info["fee_currency"], order.fee_asset)

    def test_fee_currency_is_translated_when_processing_trade_event(self):
        order = BitfinexInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "order_id": "EOID1",
            "trade_id": 1,
            "amount": 0.1,
            "price": 10050.0,
            "fee": 10.0,
            "fee_currency": "UST",
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertEqual("USDT", order.fee_asset)
