import asyncio
import unittest
from decimal import Decimal
from typing import List

from hummingbot.connector.gateway.gateway_base import GatewayBase, RetryAction
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


class GatewayBaseOrderSizeQuantumTest(unittest.TestCase):
    """Tests for get_order_size_quantum's handling of tokens missing from the token list."""

    def setUp(self) -> None:
        super().setUp()
        self.connector = MockGatewayConnector()
        self.connector._amount_quantum_dict = {"SOL": Decimal("1e-9"), "USDC": Decimal("1e-6")}

    def test_known_tokens_use_their_listed_quantum(self):
        quantum = self.connector.get_order_size_quantum("SOL-USDC", Decimal("1"))
        self.assertEqual(Decimal("1e-6"), quantum)  # max of SOL 1e-9 and USDC 1e-6

    def test_unknown_base_token_falls_back_to_six_decimals(self):
        # Memecoins are traded by mint address (symbols collide), so they don't appear in the
        # symbol-keyed token dict. This used to raise KeyError and crash the order.
        quantum = self.connector.get_order_size_quantum("PUMP-SOL", Decimal("1"))
        self.assertEqual(Decimal("1e-6"), quantum)  # max of the 1e-6 fallback and SOL 1e-9

    def test_both_tokens_unknown_falls_back_to_six_decimals(self):
        quantum = self.connector.get_order_size_quantum("PUMP-WIF", Decimal("1"))
        self.assertEqual(Decimal("1e-6"), quantum)


class GatewayBaseConnectorSettingsRegistrationTest(unittest.TestCase):
    """A Gateway connector self-registers in AllConnectorSettings so it exists whether or
    not the Gateway container / status monitor is running, without a 0.003-vs-0 fee mismatch."""

    def tearDown(self) -> None:
        from hummingbot.client.settings import AllConnectorSettings
        AllConnectorSettings.get_connector_settings().pop("test_connector", None)
        super().tearDown()

    def test_construction_alone_does_not_register(self):
        # Registration happens in start_network (after Gateway validates the name), not in
        # __init__ — so an unstarted / invalid connector never pollutes AllConnectorSettings.
        from hummingbot.client.settings import AllConnectorSettings
        AllConnectorSettings.get_connector_settings().pop("test_connector", None)
        MockGatewayConnector()
        self.assertNotIn("test_connector", AllConnectorSettings.get_connector_settings())

    def test_connector_registers_with_zero_fee_schema(self):
        from hummingbot.client.settings import AllConnectorSettings, ConnectorType
        all_settings = AllConnectorSettings.get_connector_settings()
        all_settings.pop("test_connector", None)

        MockGatewayConnector()._ensure_registered_in_connector_settings()

        self.assertIn("test_connector", all_settings)
        cs = all_settings["test_connector"]
        self.assertEqual(ConnectorType.GATEWAY_DEX, cs.type)
        self.assertEqual(Decimal("0"), cs.trade_fee_schema.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0"), cs.trade_fee_schema.taker_percent_fee_decimal)

    def test_registration_makes_build_trade_fee_not_raise(self):
        # Without registration, build_trade_fee raises "does not exist in AllConnectorSettings".
        from hummingbot.core.utils.estimate_fee import build_trade_fee
        MockGatewayConnector()._ensure_registered_in_connector_settings()
        fee = build_trade_fee(
            "test_connector", False, "SOL", "USDC", OrderType.MARKET, TradeType.SELL, Decimal("1"), Decimal("1"),
        )
        self.assertEqual(Decimal("0"), fee.percent)


class GatewayBaseRetryClassificationTest(unittest.TestCase):
    """Tests for _classify_error operation-aware retry opt-in (retryable_error_codes)."""

    def setUp(self) -> None:
        super().setUp()
        self.connector = MockGatewayConnector()

    def test_slippage_is_fail_immediate_by_default(self):
        error = Exception("Gateway error: slippage [code: SLIPPAGE_EXCEEDED]")
        action = self.connector._classify_error(error, "execute swap", 0, 10)
        self.assertEqual(RetryAction.FAIL_IMMEDIATE, action)

    def test_opted_in_code_is_retryable(self):
        # Close-position opts in to SLIPPAGE_EXCEEDED: each retry re-POSTs and Gateway
        # rebuilds from fresh on-chain state, and a landed close cannot double-spend.
        error = Exception("Gateway error: slippage [code: SLIPPAGE_EXCEEDED]")
        action = self.connector._classify_error(
            error, "close position", 0, 10, retryable_error_codes={"SLIPPAGE_EXCEEDED"}
        )
        self.assertEqual(RetryAction.RETRY, action)

    def test_opted_in_code_stops_after_max_retries(self):
        error = Exception("Gateway error: slippage [code: SLIPPAGE_EXCEEDED]")
        action = self.connector._classify_error(
            error, "close position", 10, 10, retryable_error_codes={"SLIPPAGE_EXCEEDED"}
        )
        self.assertEqual(RetryAction.STOP, action)

    def test_timeout_remains_retryable_without_opt_in(self):
        error = Exception("Gateway error: pending [code: TRANSACTION_TIMEOUT]")
        action = self.connector._classify_error(error, "execute swap", 0, 10)
        self.assertEqual(RetryAction.RETRY, action)

    def test_unknown_error_is_fail_immediate_even_with_opt_in(self):
        error = Exception("connection reset by peer")
        action = self.connector._classify_error(
            error, "close position", 0, 10, retryable_error_codes={"SLIPPAGE_EXCEEDED"}
        )
        self.assertEqual(RetryAction.FAIL_IMMEDIATE, action)


if __name__ == "__main__":
    unittest.main()
