from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.bittrex.bittrex_in_flight_order import BittrexInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class BittrexInFlightOrderTests(TestCase):

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

        order = BittrexInFlightOrder.from_json(order_info)

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

    def test_update_with_partial_trade_event(self):
        order = BittrexInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "id": "1",
            "marketSymbol": f"{self.base_token}{self.quote_token}",
            "executedAt": "12-03-2021 6:17:16",
            "quantity": "0.1",
            "rate": "10050",
            "orderId": "EOID1",
            "commission": "10",
            "isTaker": False
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("OPEN", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["quantity"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["quantity"])) * Decimal(
            str(trade_event_info["rate"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(order.quote_asset, order.fee_asset)

    def test_update_with_full_fill_trade_event(self):
        order = BittrexInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "id": "1",
            "marketSymbol": f"{self.base_token}{self.quote_token}",
            "executedAt": "12-03-2021 6:17:16",
            "quantity": "0.1",
            "rate": "10050",
            "orderId": "EOID1",
            "commission": "10",
            "isTaker": False
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("OPEN", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["quantity"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["quantity"])) * Decimal(
            str(trade_event_info["rate"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(order.quote_asset, order.fee_asset)

        complete_event_info = {
            "id": "2",
            "marketSymbol": f"{self.base_token}{self.quote_token}",
            "executedAt": "12-03-2021 6:17:16",
            "quantity": "0.9",
            "rate": "10060",
            "orderId": "EOID1",
            "commission": "50",
            "isTaker": False
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("OPEN", order.last_state)
        self.assertEqual(order.amount, order.executed_amount_base)
        expected_executed_quote_amount += Decimal(str(complete_event_info["quantity"])) * Decimal(
            str(complete_event_info["rate"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]) + Decimal(complete_event_info["commission"]),
                         order.fee_paid)

    def test_update_with_repeated_trade_id_is_ignored(self):
        order = BittrexInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "id": "1",
            "marketSymbol": f"{self.base_token}{self.quote_token}",
            "executedAt": "12-03-2021 6:17:16",
            "quantity": "0.1",
            "rate": "10050",
            "orderId": "EOID1",
            "commission": "10",
            "isTaker": False
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("OPEN", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["quantity"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["quantity"])) * Decimal(
            str(trade_event_info["rate"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(order.quote_asset, order.fee_asset)

        complete_event_info = {
            "id": "1",
            "marketSymbol": f"{self.base_token}{self.quote_token}",
            "executedAt": "12-03-2021 6:17:16",
            "quantity": "0.9",
            "rate": "10060",
            "orderId": "EOID1",
            "commission": "50",
            "isTaker": False
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertFalse(update_result)
        self.assertFalse(order.is_done)
        self.assertEqual("OPEN", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["quantity"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["quantity"])) * Decimal(
            str(trade_event_info["rate"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["commission"]), order.fee_paid)
        self.assertEqual(order.quote_asset, order.fee_asset)
