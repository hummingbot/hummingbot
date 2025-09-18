import unittest
from decimal import Decimal

from hummingbot.connector.exchange_base import ExchangeBase
from hummingbot.connector.gateway.gateway_in_flight_order import GatewayInFlightOrder
from hummingbot.connector.gateway.gateway_order_tracker import GatewayOrderTracker
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.core.data_type.common import OrderType, TradeType


class MockExchange(ExchangeBase):
    pass


class GatewayOrderTrackerTest(unittest.TestCase):
    trading_pair: str

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.trading_pair = combine_to_hb_trading_pair(base="COIN", quote="ALPHA")

    def setUp(self) -> None:
        super().setUp()

        self.connector = MockExchange()
        self.connector._set_current_timestamp(1640000000.0)
        self.tracker = GatewayOrderTracker(connector=self.connector)

    def test_all_fillable_orders_by_hash(self):
        self.tracker.start_tracking_order(
            order=GatewayInFlightOrder(
                client_order_id="1",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                creation_timestamp=1231233123,
                price=Decimal("1"),
                amount=Decimal("2"),
                exchange_order_id="asdf",
                creation_transaction_hash=None,
            )
        )
        first_creation_hash = "someHash"
        self.tracker.start_tracking_order(
            order=GatewayInFlightOrder(
                client_order_id="2",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                creation_timestamp=1231233123,
                price=Decimal("1"),
                amount=Decimal("2"),
                exchange_order_id="asdg",
                creation_transaction_hash=first_creation_hash,
            )
        )
        second_creation_hash = "anotherHash"
        cancelation_hash = "yetAnotherHash"
        self.tracker.start_tracking_order(
            order=GatewayInFlightOrder(
                client_order_id="3",
                trading_pair=self.trading_pair,
                order_type=OrderType.LIMIT,
                trade_type=TradeType.BUY,
                creation_timestamp=1231233123,
                price=Decimal("1"),
                amount=Decimal("2"),
                exchange_order_id="asde",
                creation_transaction_hash=second_creation_hash,
            )
        )
        order = self.tracker.all_orders["3"]
        order.cancel_tx_hash = cancelation_hash

        orders_by_hashes = self.tracker.all_fillable_orders_by_hash

        self.assertEqual(3, len(orders_by_hashes))
        self.assertIn(first_creation_hash, orders_by_hashes)
        self.assertIn(second_creation_hash, orders_by_hashes)
        self.assertIn(cancelation_hash, orders_by_hashes)
