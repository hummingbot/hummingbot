from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.kraken.kraken_in_flight_order import KrakenInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType


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
            creation_timestamp=1640001112.0,
            userref=1,
        )

        self.assertTrue(order.is_local)

    def test_serialize_order_to_json(self):
        order = KrakenInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(1000),
            amount=Decimal(1),
            creation_timestamp=1640001112.0,
            userref=2,
            initial_state="OPEN",
        )

        expected_json = {
            "client_order_id": order.client_order_id,
            "exchange_order_id": order.exchange_order_id,
            "trading_pair": order.trading_pair,
            "order_type": order.order_type.name,
            "trade_type": order.trade_type.name,
            "price": str(order.price),
            "amount": str(order.amount),
            "last_state": order.last_state,
            "executed_amount_base": str(order.executed_amount_base),
            "executed_amount_quote": str(order.executed_amount_quote),
            "fee_asset": order.fee_asset,
            "fee_paid": str(order.fee_paid),
            "creation_timestamp": 1640001112.0,
            "userref": order.userref,
        }

        self.assertEqual(expected_json, order.to_json())

    def test_deserialize_order_from_json(self):
        json = {
            "client_order_id": "OID1",
            "exchange_order_id": "EOID1",
            "trading_pair": "COINALPHA-HBOT",
            "order_type": OrderType.LIMIT.name,
            "trade_type": TradeType.BUY.name,
            "price": "1000",
            "amount": "1",
            "last_state": "OPEN",
            "executed_amount_base": "0.1",
            "executed_amount_quote": "110",
            "fee_asset": "BNB",
            "fee_paid": "10",
            "creation_timestamp": 1640001112.0,
            "userref": 2,
        }

        order: KrakenInFlightOrder = KrakenInFlightOrder.from_json(json)

        self.assertEqual(json["client_order_id"], order.client_order_id)
        self.assertEqual(json["exchange_order_id"], order.exchange_order_id)
        self.assertEqual(json["trading_pair"], order.trading_pair)
        self.assertEqual(OrderType.LIMIT, order.order_type)
        self.assertEqual(TradeType.BUY, order.trade_type)
        self.assertEqual(Decimal(json["price"]), order.price)
        self.assertEqual(Decimal(json["amount"]), order.amount)
        self.assertEqual(Decimal(json["executed_amount_base"]), order.executed_amount_base)
        self.assertEqual(Decimal(json["executed_amount_quote"]), order.executed_amount_quote)
        self.assertEqual(json["fee_asset"], order.fee_asset)
        self.assertEqual(Decimal(json["fee_paid"]), order.fee_paid)
        self.assertEqual(json["last_state"], order.last_state)
        self.assertEqual(json["creation_timestamp"], order.creation_timestamp)
        self.assertEqual(json["userref"], order.userref)
