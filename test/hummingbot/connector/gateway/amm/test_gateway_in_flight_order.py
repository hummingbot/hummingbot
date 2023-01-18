import asyncio
import unittest
from decimal import Decimal

from hummingbot.connector.gateway.amm.evm_in_flight_order import EVMInFlightOrder
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

    def test_order_life_cycle_of_token_approval_requests(self):
        order: EVMInFlightOrder = EVMInFlightOrder(
            client_order_id=self.client_order_id,
            trading_pair=self.quote_asset,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            creation_timestamp=1652324823,
            initial_state=OrderState.PENDING_APPROVAL,
        )
        # Assert that order is in fact a Approval Request
        self.assertTrue(order.is_approval_request)

        self.assertTrue(order.is_pending_approval)

        order_update: OrderUpdate = OrderUpdate(
            trading_pair=order.trading_pair,
            update_timestamp=1652324824,
            new_state=OrderState.APPROVED,
            client_order_id=order.client_order_id,
            exchange_order_id=self.exchange_order_id,
        )

        order.update_with_order_update(order_update=order_update)

        self.assertFalse(order.is_pending_approval)

    def test_order_life_cycle_of_trade_orders(self):
        order: EVMInFlightOrder = EVMInFlightOrder(
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
