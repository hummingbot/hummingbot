import asyncio
import unittest
from decimal import Decimal

from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate

s_decimal_0 = Decimal("0")


class GatewayInFlightOrderUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

        cls.client_order_id = "someClientOrderId"
        cls.exchange_order_id = "someTxHash"
        cls.nonce = 1

    def test_order_life_cycle_of_trade_orders(self):
        order: GatewayInFlightOrder = GatewayInFlightOrder(
            client_order_id=self.client_order_id,
            trading_pair=self.quote_asset,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("1"),
            amount=Decimal("1000"),
            creation_timestamp=1652324823,
            initial_state=OrderState.PENDING_CREATE,
        )

        # Nonce is not provided upon creation
        self.assertEqual(order.nonce, -1)

        # Exchange Order Id for GatewayInFlightOrder is only assigned after a TradeUpdate
        self.assertIsNone(order.exchange_order_id)

        # CancelTxHash is not initialized on creation

        self.assertIsNone(order.cancel_tx_hash)

    def test_update_creation_transaction_hash_with_order_update(self):
        order: GatewayInFlightOrder = GatewayInFlightOrder(
            client_order_id=self.client_order_id,
            trading_pair=self.quote_asset,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("1"),
            amount=Decimal("1000"),
            creation_timestamp=1652324823,
            initial_state=OrderState.PENDING_CREATE,
            creation_transaction_hash=None,
        )

        self.assertIsNone(order.creation_transaction_hash)

        desired_creation_transaction_hash = "someTransactionHash"
        order_update = OrderUpdate(
            trading_pair=self.trading_pair,
            update_timestamp=1652324823 + 1,
            new_state=OrderState.OPEN,
            client_order_id=self.client_order_id,
            exchange_order_id="someExchangeOrderID",
            misc_updates={
                "creation_transaction_hash": desired_creation_transaction_hash,
            }
        )
        order.update_with_order_update(order_update=order_update)

        self.assertEqual(desired_creation_transaction_hash, order.creation_transaction_hash)

    def test_update_cancelation_transaction_hash_with_order_update(self):
        order: GatewayInFlightOrder = GatewayInFlightOrder(
            client_order_id=self.client_order_id,
            trading_pair=self.quote_asset,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("1"),
            amount=Decimal("1000"),
            creation_timestamp=1652324823,
            initial_state=OrderState.PENDING_CREATE,
        )

        self.assertIsNone(order.creation_transaction_hash)

        desired_cancelation_transaction_hash = "someTransactionHash"
        order_update = OrderUpdate(
            trading_pair=self.trading_pair,
            update_timestamp=1652324823 + 1,
            new_state=OrderState.OPEN,
            client_order_id=self.client_order_id,
            exchange_order_id="someExchangeOrderID",
            misc_updates={
                "cancelation_transaction_hash": desired_cancelation_transaction_hash,
            }
        )
        order.update_with_order_update(order_update=order_update)

        self.assertEqual(desired_cancelation_transaction_hash, order.cancel_tx_hash)

    def test_to_and_from_json(self):
        base_order = GatewayInFlightOrder(
            client_order_id=self.client_order_id,
            trading_pair=self.quote_asset,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            price=Decimal("1"),
            amount=Decimal("1000"),
            creation_timestamp=1652324823,
            initial_state=OrderState.PENDING_CREATE,
        )
        base_order.last_update_timestamp = 1652324824

        order_json = base_order.to_json()
        derived_order = GatewayInFlightOrder.from_json(order_json)

        self.assertEqual(base_order, derived_order)
