from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.connector.balancer.balancer_in_flight_order import BalancerInFlightOrder
from hummingbot.core.event.events import OrderType, TradeType


class BalancerInFlightOrderTests(TestCase):

    def test_deserialize_order_from_json(self):
        json = {
            "client_order_id": "OID1",
            "exchange_order_id": "EOID",
            "trading_pair": "COINALPHA-HBOT",
            "order_type": OrderType.LIMIT.name,
            "trade_type": TradeType.BUY.name,
            "price": "1000.0",
            "amount": "1.0",
            "executed_amount_base": "0.5",
            "executed_amount_quote": "510.0",
            "fee_asset": "BNB",
            "fee_paid": "10.0",
            "last_state": "OPEN",
            "creation_timestamp": 1640001112.0
        }

        order = BalancerInFlightOrder.from_json(json)

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
        self.assertEqual(json["creation_timestamp"], 1640001112.0)
        self.assertIsNone(order.gas_price)
