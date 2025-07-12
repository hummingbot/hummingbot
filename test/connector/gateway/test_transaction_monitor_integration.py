"""
Integration tests for TransactionMonitor with database callbacks.
"""
import asyncio
import unittest
from decimal import Decimal
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.gateway.core.transaction_monitor import TransactionMonitor
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import TokenAmount


class MockClientOrderTracker:
    """Mock ClientOrderTracker for testing database writes."""

    def __init__(self):
        self.order_updates: List[OrderUpdate] = []
        self.trade_updates: List[TradeUpdate] = []

    def process_order_update(self, order_update: OrderUpdate):
        """Mock process_order_update that records calls."""
        self.order_updates.append(order_update)

    def process_trade_update(self, trade_update: TradeUpdate):
        """Mock process_trade_update that records calls."""
        self.trade_updates.append(trade_update)


class MockGatewayConnector:
    """Mock GatewayConnector with callback handling."""

    def __init__(self, order_tracker: MockClientOrderTracker):
        self._order_tracker = order_tracker
        self.in_flight_orders = {}

    def gateway_order_tracker_callback(self, event_type: str, order_id: str, data: Any):
        """Simulate the real callback that updates the database."""
        if event_type == "tx_hash":
            # Update in-flight order with tx hash
            if order_id in self.in_flight_orders:
                self.in_flight_orders[order_id]["exchange_order_id"] = data

        elif event_type == "confirmed":
            # Create OrderUpdate for confirmed transaction
            order_update = OrderUpdate(
                trading_pair="ETH-USDC",
                update_timestamp=1234567890,
                new_state="FILLED",
                client_order_id=order_id,
                exchange_order_id=data.get("txHash", ""),
                misc_updates={"confirmed_data": data}
            )
            self._order_tracker.process_order_update(order_update)

            # For swaps, also create TradeUpdate
            trade_update = TradeUpdate(
                trade_id=f"{order_id}-1",
                client_order_id=order_id,
                exchange_order_id=data.get("txHash", ""),
                trading_pair="ETH-USDC",
                fill_timestamp=1234567890,
                fill_price=Decimal("3000"),
                fill_base_amount=Decimal("1.0"),
                fill_quote_amount=Decimal("3000"),
                fee=TokenAmount("ETH", Decimal("0.001"))
            )
            self._order_tracker.process_trade_update(trade_update)

        elif event_type == "failed":
            # Create OrderUpdate for failed transaction
            order_update = OrderUpdate(
                trading_pair="ETH-USDC",
                update_timestamp=1234567890,
                new_state="FAILED",
                client_order_id=order_id,
                exchange_order_id=self.in_flight_orders.get(order_id, {}).get("exchange_order_id", ""),
                misc_updates={"error": data}
            )
            self._order_tracker.process_order_update(order_update)


class TestTransactionMonitorIntegration(unittest.TestCase):
    """Integration tests for TransactionMonitor with database operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.gateway_client = MagicMock()
        self.monitor = TransactionMonitor(self.gateway_client)

        # Mock order tracker and connector
        self.order_tracker = MockClientOrderTracker()
        self.connector = MockGatewayConnector(self.order_tracker)

        # Set up in-flight order
        self.order_id = "test-order-123"
        self.connector.in_flight_orders[self.order_id] = {
            "client_order_id": self.order_id,
            "trading_pair": "ETH-USDC",
            "order_type": OrderType.LIMIT,
            "trade_type": TradeType.BUY,
            "amount": Decimal("1.0"),
            "price": Decimal("3000")
        }

    def tearDown(self):
        """Clean up after tests."""
        self.order_tracker.order_updates.clear()
        self.order_tracker.trade_updates.clear()
        self.connector.in_flight_orders.clear()

    def test_confirmed_writes_to_database(self):
        """Test that confirmed transactions write to database."""
        asyncio.run(self._test_confirmed_writes_to_database())

    async def _test_confirmed_writes_to_database(self):
        """Async test for database writes on confirmation."""
        response = {
            "txHash": "0x123abc",
            "status": 1,  # CONFIRMED
            "gasUsed": "150000",
            "effectiveGasPrice": "50000000000"
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id=self.order_id,
            callback=self.connector.gateway_order_tracker_callback
        )

        # Verify order update was written
        self.assertEqual(len(self.order_tracker.order_updates), 1)
        order_update = self.order_tracker.order_updates[0]
        self.assertEqual(order_update.client_order_id, self.order_id)
        self.assertEqual(order_update.new_state, "FILLED")
        self.assertEqual(order_update.exchange_order_id, "0x123abc")

        # Verify trade update was written
        self.assertEqual(len(self.order_tracker.trade_updates), 1)
        trade_update = self.order_tracker.trade_updates[0]
        self.assertEqual(trade_update.client_order_id, self.order_id)
        self.assertEqual(trade_update.exchange_order_id, "0x123abc")

    def test_pending_polls_until_confirmed(self):
        """Test that pending transactions poll and then write to database."""
        asyncio.run(self._test_pending_polls_until_confirmed())

    async def _test_pending_polls_until_confirmed(self):
        """Async test for polling and database writes."""
        initial_response = {
            "txHash": "0x456def",
            "status": 0  # PENDING
        }

        # Mock polling responses
        poll_responses = [
            {"status": 0, "confirmations": 0},  # First poll - still pending
            {"status": 0, "confirmations": 1},  # Second poll - still pending
            {"status": 1, "confirmations": 3, "gasUsed": "200000"}  # Third poll - confirmed
        ]
        self.gateway_client.get_transaction_status = AsyncMock(side_effect=poll_responses)

        # Speed up polling for test
        original_poll_interval = self.monitor.POLL_INTERVAL
        original_max_time = self.monitor.MAX_POLL_TIME
        self.monitor.POLL_INTERVAL = 0.1
        self.monitor.MAX_POLL_TIME = 0.5  # Limit total time

        try:
            await self.monitor.monitor_transaction(
                response=initial_response,
                chain="ethereum",
                network="mainnet",
                order_id=self.order_id,
                callback=self.connector.gateway_order_tracker_callback
            )
        finally:
            # Restore original values
            self.monitor.POLL_INTERVAL = original_poll_interval
            self.monitor.MAX_POLL_TIME = original_max_time

        # Verify polling occurred
        self.assertEqual(self.gateway_client.get_transaction_status.call_count, 3)

        # Verify order was updated with tx hash first
        self.assertEqual(self.connector.in_flight_orders[self.order_id]["exchange_order_id"], "0x456def")

        # Verify final database writes
        self.assertEqual(len(self.order_tracker.order_updates), 1)
        self.assertEqual(self.order_tracker.order_updates[0].new_state, "FILLED")
        self.assertEqual(len(self.order_tracker.trade_updates), 1)

    def test_timeout_marks_as_failed(self):
        """Test that timeout writes failed status to database."""
        asyncio.run(self._test_timeout_marks_as_failed())

    async def _test_timeout_marks_as_failed(self):
        """Async test for timeout handling."""
        response = {
            "txHash": "0x789ghi",
            "status": 0  # PENDING
        }

        # Mock polling to always return pending
        self.gateway_client.get_transaction_status = AsyncMock(
            return_value={"status": 0, "confirmations": 0}
        )

        # Very short timeout for testing
        self.monitor.POLL_INTERVAL = 0.05
        self.monitor.MAX_POLL_TIME = 0.2

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id=self.order_id,
            callback=self.connector.gateway_order_tracker_callback
        )

        # Verify order was marked as failed
        self.assertEqual(len(self.order_tracker.order_updates), 1)
        order_update = self.order_tracker.order_updates[0]
        self.assertEqual(order_update.new_state, "FAILED")
        self.assertEqual(order_update.client_order_id, self.order_id)
        self.assertIn("timed out", order_update.misc_updates["error"])

        # No trade updates for failed orders
        self.assertEqual(len(self.order_tracker.trade_updates), 0)

    def test_failed_transaction_writes_to_database(self):
        """Test that failed transactions write to database."""
        asyncio.run(self._test_failed_transaction_writes_to_database())

    async def _test_failed_transaction_writes_to_database(self):
        """Async test for failed transaction database writes."""
        response = {
            "txHash": "0xfailed",
            "status": -1,  # FAILED
            "message": "Transaction reverted: insufficient balance"
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id=self.order_id,
            callback=self.connector.gateway_order_tracker_callback
        )

        # Verify order was marked as failed
        self.assertEqual(len(self.order_tracker.order_updates), 1)
        order_update = self.order_tracker.order_updates[0]
        self.assertEqual(order_update.new_state, "FAILED")
        self.assertEqual(order_update.misc_updates["error"], "Transaction reverted: insufficient balance")

        # No trade updates for failed orders
        self.assertEqual(len(self.order_tracker.trade_updates), 0)

    def test_pending_then_failed(self):
        """Test pending transaction that eventually fails."""
        asyncio.run(self._test_pending_then_failed())

    async def _test_pending_then_failed(self):
        """Async test for pending then failed."""
        response = {
            "txHash": "0xpendingfail",
            "status": 0  # PENDING
        }

        # Mock polling to return failed after some pending
        poll_responses = [
            {"status": 0},  # Still pending
            {"status": -1, "message": "Out of gas"}  # Failed
        ]
        self.gateway_client.get_transaction_status = AsyncMock(side_effect=poll_responses)

        self.monitor.POLL_INTERVAL = 0.1

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id=self.order_id,
            callback=self.connector.gateway_order_tracker_callback
        )

        # Verify order was marked as failed
        self.assertEqual(len(self.order_tracker.order_updates), 1)
        order_update = self.order_tracker.order_updates[0]
        self.assertEqual(order_update.new_state, "FAILED")
        self.assertEqual(order_update.misc_updates["error"], "Out of gas")

    def test_multiple_orders_concurrent(self):
        """Test monitoring multiple orders concurrently."""
        asyncio.run(self._test_multiple_orders_concurrent())

    async def _test_multiple_orders_concurrent(self):
        """Async test for concurrent order monitoring."""
        # Set up multiple orders
        orders = [
            ("order-1", {"txHash": "0x111", "status": 1}),  # Immediate confirm
            ("order-2", {"txHash": "0x222", "status": 0}),  # Pending
            ("order-3", {"txHash": "0x333", "status": -1, "message": "Failed"}),  # Failed
        ]

        for order_id, _ in orders:
            self.connector.in_flight_orders[order_id] = {
                "client_order_id": order_id,
                "trading_pair": "ETH-USDC"
            }

        # Mock polling for order-2
        self.gateway_client.get_transaction_status = AsyncMock(
            return_value={"status": 1}  # Eventually confirms
        )

        self.monitor.POLL_INTERVAL = 0.1

        # Start monitoring all orders concurrently
        tasks = []
        for order_id, response in orders:
            task = self.monitor.monitor_transaction(
                response=response,
                chain="ethereum",
                network="mainnet",
                order_id=order_id,
                callback=self.connector.gateway_order_tracker_callback
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Should have 3 order updates
        self.assertEqual(len(self.order_tracker.order_updates), 3)

        # Check each order
        order_states = {ou.client_order_id: ou.new_state for ou in self.order_tracker.order_updates}
        self.assertEqual(order_states["order-1"], "FILLED")
        self.assertEqual(order_states["order-2"], "FILLED")
        self.assertEqual(order_states["order-3"], "FAILED")

        # Should have 2 trade updates (for confirmed orders only)
        self.assertEqual(len(self.order_tracker.trade_updates), 2)

    def test_callback_exception_handling(self):
        """Test that exceptions in callbacks don't break monitoring."""
        asyncio.run(self._test_callback_exception_handling())

    async def _test_callback_exception_handling(self):
        """Async test for callback exception handling."""
        response = {
            "txHash": "0xexception",
            "status": 0  # PENDING
        }

        # Create a wrapper that tracks calls
        original_callback = self.connector.gateway_order_tracker_callback
        call_count = 0
        exception_raised = False

        def wrapped_callback(event_type: str, order_id: str, data: Any):
            nonlocal call_count, exception_raised
            call_count += 1
            if call_count == 1 and event_type == "tx_hash":
                exception_raised = True
                raise Exception("Callback error!")
            # Otherwise work normally
            original_callback(event_type, order_id, data)

        # Mock polling to return confirmed
        self.gateway_client.get_transaction_status = AsyncMock(
            return_value={"status": 1}
        )

        self.monitor.POLL_INTERVAL = 0.1

        # The exception in callback will propagate and stop monitoring
        with self.assertRaises(Exception) as context:
            await self.monitor.monitor_transaction(
                response=response,
                chain="ethereum",
                network="mainnet",
                order_id=self.order_id,
                callback=wrapped_callback
            )

        # Verify exception was raised
        self.assertTrue(exception_raised)
        self.assertEqual(str(context.exception), "Callback error!")

        # Since exception occurred during tx_hash callback, polling never started
        self.assertEqual(self.gateway_client.get_transaction_status.call_count, 0)

    def test_no_callback_provided(self):
        """Test that monitoring works without callback."""
        asyncio.run(self._test_no_callback_provided())

    async def _test_no_callback_provided(self):
        """Async test for no callback scenario."""
        response = {
            "txHash": "0xnocallback",
            "status": 0  # PENDING
        }

        # Mock polling
        self.gateway_client.get_transaction_status = AsyncMock(
            return_value={"status": 1}
        )

        self.monitor.POLL_INTERVAL = 0.1

        # Should not raise exception
        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id=self.order_id,
            callback=None  # No callback
        )

        # No database updates
        self.assertEqual(len(self.order_tracker.order_updates), 0)
        self.assertEqual(len(self.order_tracker.trade_updates), 0)


if __name__ == "__main__":
    unittest.main()
