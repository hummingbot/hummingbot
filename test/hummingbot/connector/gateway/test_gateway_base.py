import asyncio
import unittest
from decimal import Decimal
from typing import List

from hummingbot.connector.gateway.gateway_base import GatewayBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee, TokenAmount
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketEvent, SellOrderCreatedEvent


class MockGatewayConnector(GatewayBase):
    """Mock Gateway connector for testing."""

    def __init__(self):
        super().__init__(
            connector_name="test_connector",
            chain="solana",
            network="mainnet-beta",
            address="test_address",
            trading_pairs=["SOL-USDC"],
            trading_required=True,
        )
        self._name = "solana-mainnet-beta"
        self._native_currency = "SOL"

    @property
    def name(self) -> str:
        return self._name


class GatewayBaseEventOrderingTest(unittest.TestCase):
    """Tests for Gateway connector event ordering to prevent regression."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.ev_loop)

        cls.base_asset = "SOL"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.connector = MockGatewayConnector()
        self.connector._set_current_timestamp(1640000000.0)
        self._initialize_event_loggers()
        self.events_received: List[str] = []

    def _initialize_event_loggers(self):
        """Set up event loggers to track event order."""
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()
        self.order_filled_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
        ]

        for event, logger in events_and_loggers:
            self.connector.add_listener(event, logger)

    def async_run_with_timeout(self, coroutine, timeout: float = 1):
        return self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))

    def test_start_tracking_order_emits_order_created_event_for_buy(self):
        """Verify that start_tracking_order emits OrderCreated event immediately for buy orders."""
        order_id = "buy-SOL-USDC-123456"

        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=False,
        )

        # Check BuyOrderCreatedEvent was emitted
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))
        event = self.buy_order_created_logger.event_log[0]
        self.assertIsInstance(event, BuyOrderCreatedEvent)
        self.assertEqual(event.order_id, order_id)
        self.assertEqual(event.trading_pair, self.trading_pair)
        self.assertEqual(event.amount, Decimal("1.0"))

    def test_start_tracking_order_emits_order_created_event_for_sell(self):
        """Verify that start_tracking_order emits OrderCreated event immediately for sell orders."""
        order_id = "sell-SOL-USDC-123456"

        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.SELL,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=False,
        )

        # Check SellOrderCreatedEvent was emitted
        self.assertEqual(1, len(self.sell_order_created_logger.event_log))
        event = self.sell_order_created_logger.event_log[0]
        self.assertIsInstance(event, SellOrderCreatedEvent)
        self.assertEqual(event.order_id, order_id)

    def test_start_tracking_order_does_not_emit_event_for_approval(self):
        """Verify that approval orders do not emit OrderCreated event."""
        order_id = "approve-SOL-123456"

        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("0"),
            amount=Decimal("0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=True,
        )

        # No OrderCreated event should be emitted for approvals
        self.assertEqual(0, len(self.buy_order_created_logger.event_log))
        self.assertEqual(0, len(self.sell_order_created_logger.event_log))

    def test_start_tracking_order_sets_state_to_open(self):
        """Verify that order state is OPEN after start_tracking_order (not PENDING_CREATE)."""
        order_id = "buy-SOL-USDC-123456"

        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=False,
        )

        # Order should be in OPEN state, not PENDING_CREATE
        order = self.connector._order_tracker.fetch_order(order_id)
        self.assertIsNotNone(order)
        self.assertEqual(order.current_state, OrderState.OPEN)
        self.assertTrue(order.is_open)

    def test_approval_order_stays_in_pending_approval_state(self):
        """Verify that approval orders remain in PENDING_APPROVAL state."""
        order_id = "approve-SOL-123456"

        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("0"),
            amount=Decimal("0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=True,
        )

        order = self.connector._order_tracker.fetch_order(order_id)
        self.assertIsNotNone(order)
        self.assertEqual(order.current_state, OrderState.PENDING_APPROVAL)

    def test_no_duplicate_order_created_on_order_update(self):
        """Verify that process_order_update does not emit duplicate OrderCreated event."""
        order_id = "buy-SOL-USDC-123456"

        # Start tracking emits OrderCreated
        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=False,
        )

        self.assertEqual(1, len(self.buy_order_created_logger.event_log))

        # Process order update to FILLED state
        order_update = OrderUpdate(
            client_order_id=order_id,
            exchange_order_id="tx_hash_123",
            trading_pair=self.trading_pair,
            update_timestamp=self.connector.current_timestamp,
            new_state=OrderState.FILLED,
        )

        # Force the order to be considered completely filled
        order = self.connector._order_tracker.fetch_order(order_id)
        order.completely_filled_event.set()

        update_future = self.connector._order_tracker.process_order_update(order_update)
        self.async_run_with_timeout(update_future)

        # Should still only have 1 OrderCreated event (no duplicate)
        self.assertEqual(1, len(self.buy_order_created_logger.event_log))

    def test_order_filled_event_after_order_created(self):
        """Verify OrderFilled comes after OrderCreated in the event sequence."""
        order_id = "buy-SOL-USDC-123456"
        events_order = []

        # Custom listener to track event order
        def on_buy_created(event_tag, connector, event):
            events_order.append("BuyOrderCreated")

        def on_order_filled(event_tag, connector, event):
            events_order.append("OrderFilled")

        from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder
        created_forwarder = SourceInfoEventForwarder(on_buy_created)
        filled_forwarder = SourceInfoEventForwarder(on_order_filled)

        self.connector.add_listener(MarketEvent.BuyOrderCreated, created_forwarder)
        self.connector.add_listener(MarketEvent.OrderFilled, filled_forwarder)

        # Start tracking - emits OrderCreated
        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=False,
        )

        # Process trade update - emits OrderFilled
        trade_update = TradeUpdate(
            trade_id="tx_hash_123",
            client_order_id=order_id,
            exchange_order_id="tx_hash_123",
            trading_pair=self.trading_pair,
            fill_timestamp=self.connector.current_timestamp,
            fill_price=Decimal("100"),
            fill_base_amount=Decimal("1.0"),
            fill_quote_amount=Decimal("100"),
            fee=AddedToCostTradeFee(flat_fees=[TokenAmount("SOL", Decimal("0.001"))]),
        )

        self.connector._order_tracker.process_trade_update(trade_update)

        # Verify event order: OrderCreated should come before OrderFilled
        self.assertEqual(["BuyOrderCreated", "OrderFilled"], events_order)

    def test_full_swap_lifecycle_event_order(self):
        """
        Test the complete swap lifecycle event ordering:
        1. OrderCreated (when order starts tracking)
        2. OrderCompleted (when order state transitions to FILLED)
        3. OrderFilled (when trade update is processed)

        This ensures external systems (like databases) receive events in the correct order.
        """
        order_id = "buy-SOL-USDC-123456"
        events_order = []

        from hummingbot.core.event.event_forwarder import SourceInfoEventForwarder

        def on_buy_created(event_tag, connector, event):
            events_order.append("BuyOrderCreated")

        def on_order_filled(event_tag, connector, event):
            events_order.append("OrderFilled")

        def on_buy_completed(event_tag, connector, event):
            events_order.append("BuyOrderCompleted")

        created_forwarder = SourceInfoEventForwarder(on_buy_created)
        filled_forwarder = SourceInfoEventForwarder(on_order_filled)
        completed_forwarder = SourceInfoEventForwarder(on_buy_completed)

        self.connector.add_listener(MarketEvent.BuyOrderCreated, created_forwarder)
        self.connector.add_listener(MarketEvent.OrderFilled, filled_forwarder)
        self.connector.add_listener(MarketEvent.BuyOrderCompleted, completed_forwarder)

        # Step 1: Start tracking order (emits OrderCreated)
        self.connector.start_tracking_order(
            order_id=order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("100"),
            amount=Decimal("1.0"),
            order_type=OrderType.AMM_SWAP,
            is_approval=False,
        )

        # Step 2: Process order update to FILLED (emits OrderCompleted)
        order = self.connector._order_tracker.fetch_order(order_id)
        order.completely_filled_event.set()

        order_update = OrderUpdate(
            client_order_id=order_id,
            exchange_order_id="tx_hash_123",
            trading_pair=self.trading_pair,
            update_timestamp=self.connector.current_timestamp,
            new_state=OrderState.FILLED,
        )
        update_future = self.connector._order_tracker.process_order_update(order_update)
        self.async_run_with_timeout(update_future)

        # Step 3: Process trade update (emits OrderFilled)
        trade_update = TradeUpdate(
            trade_id="tx_hash_123",
            client_order_id=order_id,
            exchange_order_id="tx_hash_123",
            trading_pair=self.trading_pair,
            fill_timestamp=self.connector.current_timestamp,
            fill_price=Decimal("100"),
            fill_base_amount=Decimal("1.0"),
            fill_quote_amount=Decimal("100"),
            fee=AddedToCostTradeFee(flat_fees=[TokenAmount("SOL", Decimal("0.001"))]),
        )
        self.connector._order_tracker.process_trade_update(trade_update)

        # Verify event order
        self.assertEqual(
            ["BuyOrderCreated", "BuyOrderCompleted", "OrderFilled"],
            events_order,
            "Events must be emitted in order: OrderCreated -> OrderCompleted -> OrderFilled"
        )


if __name__ == "__main__":
    unittest.main()
