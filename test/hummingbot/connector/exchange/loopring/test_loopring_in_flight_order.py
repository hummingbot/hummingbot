from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.exchange.loopring.loopring_in_flight_order import LoopringInFlightOrder
from hummingbot.connector.exchange.loopring.loopring_order_status import LoopringOrderStatus
from hummingbot.core.event.events import OrderType, TradeType


class LoopringInFlightOrderTests(TestCase):

    def test_serialize_order_to_json(self):
        order = LoopringInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(1000),
            amount=Decimal(1),
            initial_state=LoopringOrderStatus.processing,
            filled_size=Decimal("0.1"),
            filled_volume=Decimal("110"),
            filled_fee=Decimal(10),
            created_at=1640001112.0,
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
            "last_state": LoopringOrderStatus.processing.name,
            "executed_amount_base": "0.1",
            "executed_amount_quote": "110",
            "fee_asset": "BNB",
            "fee_paid": "10",
            "creation_timestamp": 1640001112.0,
        }

        order: LoopringInFlightOrder = LoopringInFlightOrder.from_json(json)

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
        self.assertEqual(LoopringOrderStatus[json["last_state"]], order.status)
        self.assertEqual(json["creation_timestamp"], order.creation_timestamp)
