from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.huobi.huobi_in_flight_order import HuobiInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class HuobiInFlightOrderTests(TestCase):

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

        order = HuobiInFlightOrder.from_json(order_info)

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
        order = HuobiInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="99998888",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "eventType": "trade",
            "symbol": "btcusdt",
            "orderId": 99998888,
            "tradePrice": "10050.0",
            "tradeVolume": "0.1",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 1,
            "tradeTime": 998787897878,
            "transactFee": "10.00",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual("partial-filled", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["tradeVolume"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["tradeVolume"])) * Decimal(
            str(trade_event_info["tradePrice"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["transactFee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"].upper(), order.fee_asset)

    def test_update_with_full_fill_trade_event(self):
        order = HuobiInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="99998888",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "eventType": "trade",
            "symbol": "btcusdt",
            "orderId": 99998888,
            "tradePrice": "10050.0",
            "tradeVolume": "0.1",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 1,
            "tradeTime": 998787897878,
            "transactFee": "10.00",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual("partial-filled", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["tradeVolume"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["tradeVolume"])) * Decimal(
            str(trade_event_info["tradePrice"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["transactFee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"].upper(), order.fee_asset)

        complete_event_info = {
            "eventType": "trade",
            "symbol": "btcusdt",
            "orderId": 99998888,
            "tradePrice": "10060.0",
            "tradeVolume": "0.9",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 2,
            "tradeTime": 998787897878,
            "transactFee": "50.00",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertTrue(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual("partial-filled", order.last_state)
        self.assertEqual(order.amount, order.executed_amount_base)
        expected_executed_quote_amount += Decimal(str(complete_event_info["tradeVolume"])) * Decimal(
            str(complete_event_info["tradePrice"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["transactFee"]) + Decimal(complete_event_info["transactFee"]),
                         order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"].upper(), order.fee_asset)

    def test_update_with_repeated_trade_id_is_ignored(self):
        order = HuobiInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="99998888",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(10000),
            amount=Decimal(1)
        )

        trade_event_info = {
            "eventType": "trade",
            "symbol": "btcusdt",
            "orderId": 99998888,
            "tradePrice": "10050.0",
            "tradeVolume": "0.1",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 1,
            "tradeTime": 998787897878,
            "transactFee": "10.00",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        update_result = order.update_with_trade_update(trade_event_info)

        self.assertTrue(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual("partial-filled", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["tradeVolume"])), order.executed_amount_base)
        expected_executed_quote_amount = Decimal(str(trade_event_info["tradeVolume"])) * Decimal(
            str(trade_event_info["tradePrice"]))
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["transactFee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"].upper(), order.fee_asset)

        complete_event_info = {
            "eventType": "trade",
            "symbol": "btcusdt",
            "orderId": 99998888,
            "tradePrice": "10060.0",
            "tradeVolume": "0.9",
            "orderSide": "buy",
            "aggressor": True,
            "tradeId": 1,
            "tradeTime": 998787897878,
            "transactFee": "50.00",
            "feeDeduct ": "0",
            "feeDeductType": "",
            "feeCurrency": "usdt",
            "accountId": 9912791,
            "source": "spot-api",
            "orderPrice": "10000",
            "orderSize": "1",
            "clientOrderId": "OID1",
            "orderCreateTime": 998787897878,
            "orderStatus": "partial-filled"
        }

        update_result = order.update_with_trade_update(complete_event_info)

        self.assertFalse(update_result)
        self.assertTrue(order.is_open)
        self.assertEqual("partial-filled", order.last_state)
        self.assertEqual(Decimal(str(trade_event_info["tradeVolume"])), order.executed_amount_base)
        self.assertEqual(expected_executed_quote_amount, order.executed_amount_quote)
        self.assertEqual(Decimal(trade_event_info["transactFee"]), order.fee_paid)
        self.assertEqual(trade_event_info["feeCurrency"].upper(), order.fee_asset)
