from decimal import Decimal
from unittest import TestCase

from hummingbot.connector.in_flight_order_base import InFlightOrderBase
from hummingbot.core.data_type.in_flight_order import OrderState
from hummingbot.core.event.events import LimitOrderStatus, OrderType, TradeType


class InFlightOrderBaseTests(TestCase):

    def test_string_repr(self):
        order = InFlightOrderBase(
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

        expected_repr = ("InFlightOrder(client_order_id='OID1', exchange_order_id='EOID1', "
                         "creation_timestamp=1640001112, trading_pair='COINALPHA-HBOT', order_type=OrderType.LIMIT, "
                         "trade_type=TradeType.BUY, price=1000, amount=1, executed_amount_base=0, "
                         "executed_amount_quote=0, fee_asset='None', fee_paid=0, last_state='PENDING_CREATE')")

        self.assertEqual(expected_repr, repr(order))

    def test_get_creation_timestamp(self):
        order = InFlightOrderBase(
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

        self.assertEqual(1640001112, order.creation_timestamp)

    def test_creation_timestamp_taken_from_order_id_when_not_specified(self):
        order = InFlightOrderBase(
            client_order_id="OID1-1640001112223334",
            exchange_order_id="EOID1",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(1000),
            amount=Decimal(1),
            creation_timestamp=-1,
            initial_state=OrderState.PENDING_CREATE.name
        )

        self.assertEqual(1640001112.223334, order.creation_timestamp)

    def test_serialize_order_to_json(self):
        order = InFlightOrderBase(
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

        order = InFlightOrderBase.from_json(json)

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

    def test_to_limit_order(self):
        order = InFlightOrderBase(
            client_order_id="OID1",
            exchange_order_id="EOID1",
            trading_pair="COINALPHA-HBOT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal(1000),
            amount=Decimal(1),
            initial_state=OrderState.PENDING_CREATE.name,
            creation_timestamp=1640001112.223330
        )

        limit_order = order.to_limit_order()

        self.assertEqual("OID1", limit_order.client_order_id)
        self.assertEqual("COINALPHA-HBOT", limit_order.trading_pair)
        self.assertTrue(limit_order.is_buy)
        self.assertEqual("COINALPHA", limit_order.base_currency)
        self.assertEqual("HBOT", limit_order.quote_currency)
        self.assertEqual(Decimal(1000), limit_order.price)
        self.assertEqual(Decimal(1), limit_order.quantity)
        self.assertTrue(limit_order.filled_quantity.is_nan())
        self.assertEqual(1640001112223330, limit_order.creation_timestamp)
        self.assertEqual(LimitOrderStatus.UNKNOWN, limit_order.status)
