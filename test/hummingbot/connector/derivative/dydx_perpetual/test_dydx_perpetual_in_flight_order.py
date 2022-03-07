from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_fill_report import DydxPerpetualFillReport
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_in_flight_order import DydxPerpetualInFlightOrder
from hummingbot.connector.derivative.dydx_perpetual.dydx_perpetual_order_status import DydxPerpetualOrderStatus
from hummingbot.core.event.events import OrderType, TradeType


class DydxPerpetualInFlightOrderTests(TestCase):

    def test_serialize_order_to_json(self):
        order = DydxPerpetualInFlightOrder(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(1000),
            amount=Decimal(1),
            initial_state=DydxPerpetualOrderStatus.PENDING,
            filled_size=Decimal("0.1"),
            filled_volume=Decimal("110"),
            filled_fee=Decimal(10),
            created_at=1640001112.0,
            leverage=1,
            position="Position"
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
            "status": order.status.name,
            "executed_amount_base": str(order.executed_amount_base),
            "executed_amount_quote": str(order.executed_amount_quote),
            "fee_asset": order.fee_asset,
            "fee_paid": str(order.fee_paid),
            "creation_timestamp": order.creation_timestamp,
            "leverage": order.leverage,
            "position": order.position,
            "fills": [],
            "_last_executed_amount_from_order_status": str(order._last_executed_amount_from_order_status),
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
            "last_state": DydxPerpetualOrderStatus.OPEN.name,
            "status": DydxPerpetualOrderStatus.OPEN.name,
            "executed_amount_base": "0.1",
            "executed_amount_quote": "110",
            "fee_asset": "BNB",
            "fee_paid": "10",
            "creation_timestamp": 1640001112.0,
            "leverage": 1,
            "position": "Position",
            "fills": [],
            "_last_executed_amount_from_order_status": "0.1",
        }

        order: DydxPerpetualInFlightOrder = DydxPerpetualInFlightOrder.from_json(json)

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
        self.assertEqual(DydxPerpetualOrderStatus[json["status"]], order.status)
        self.assertEqual(json["creation_timestamp"], order.creation_timestamp)
        self.assertEqual(json["leverage"], order.leverage)
        self.assertEqual(json["position"], order.position)
        self.assertEqual(0, len(order.fills))
        self.assertEqual(
            Decimal(json["_last_executed_amount_from_order_status"]),
            order._last_executed_amount_from_order_status)

    def test_deserialize_order_with_fills_from_json(self):
        json = {
            "client_order_id": "OID1",
            "exchange_order_id": "EOID1",
            "trading_pair": "COINALPHA-HBOT",
            "order_type": OrderType.LIMIT.name,
            "trade_type": TradeType.BUY.name,
            "price": "1000",
            "amount": "1",
            "last_state": DydxPerpetualOrderStatus.OPEN.name,
            "status": DydxPerpetualOrderStatus.OPEN.name,
            "executed_amount_base": "0.1",
            "executed_amount_quote": "110",
            "fee_asset": "BNB",
            "fee_paid": "10",
            "creation_timestamp": 1640001112.0,
            "leverage": 1,
            "position": "Position",
            "fills": [{
                "id": "fill_id_1",
                "amount": "2",
                "price": "998.5",
                "fee": "10",
            }],
            "_last_executed_amount_from_order_status": "0.1",
        }

        order: DydxPerpetualInFlightOrder = DydxPerpetualInFlightOrder.from_json(json)

        self.assertEqual(1, len(order.fills))
        fill: DydxPerpetualFillReport = next((fill for fill in order.fills))
        self.assertEqual("fill_id_1", fill.id)
        self.assertEqual(Decimal("2"), fill.amount)
        self.assertEqual(Decimal("998.5"), fill.price)
        self.assertEqual(Decimal("10"), fill.fee)
