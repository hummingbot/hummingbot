from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.crypto_com.crypto_com_in_flight_order import CryptoComInFlightOrder
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.event.events import OrderType, TradeType


class CryptoComInnFlightOrderTests(TestCase):

    def test_serialize_order_to_json(self):
        order = CryptoComInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(1000),
            amount=Decimal(1),
            initial_state=OrderState.PENDING_CREATE.name,
            creation_timestamp=1640001112.0
        )

        expected_json = {
            "client_order_id": order.client_order_id,
            "exchange_order_id": order.exchange_order_id,
            "trading_pair": order.trading_pair,
            "order_type": order.order_type.name,
            "trade_type": order.trade_type.name,
            "price": str(order.price),
            "amount": str(order.amount),
            "executed_amount_base": str(order.executed_amount_base),
            "executed_amount_quote": str(order.executed_amount_quote),
            "fee_asset": order.fee_asset,
            "fee_paid": str(order.fee_paid),
            "last_state": order.last_state,
            "creation_timestamp": order.creation_timestamp
        }

        self.assertEqual(expected_json, order.to_json())

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
            "last_state": OrderState.PARTIALLY_FILLED.name,
            "creation_timestamp": 1640001112.0
        }

        order = CryptoComInFlightOrder.from_json(json)

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
        self.assertEqual(OrderState.PARTIALLY_FILLED.name, order.last_state)
        self.assertEqual(json["creation_timestamp"], order.creation_timestamp)
