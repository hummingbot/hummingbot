"""
Test transaction monitor functionality.
"""
import asyncio
import unittest
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.gateway.core.transaction_monitor import TransactionMonitor


class TestTransactionMonitor(unittest.TestCase):
    """Test TransactionMonitor class."""

    def setUp(self):
        """Set up test fixtures."""
        self.gateway_client = MagicMock()
        self.monitor = TransactionMonitor(self.gateway_client)
        self.callback_events: List[tuple] = []

    def tearDown(self):
        """Clean up after tests."""
        self.callback_events.clear()

    def mock_callback(self, event_type: str, order_id: str, data: Any):
        """Mock callback to track events."""
        self.callback_events.append((event_type, order_id, data))

    async def async_mock_callback(self, event_type: str, order_id: str, data: Any):
        """Async mock callback."""
        self.mock_callback(event_type, order_id, data)

    def test_immediate_confirmed(self):
        """Test transaction that is immediately confirmed."""
        asyncio.run(self._test_immediate_confirmed())

    async def _test_immediate_confirmed(self):
        """Async test for immediate confirmation."""
        response = {
            "signature": "0x123abc",
            "status": 1  # CONFIRMED
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-order-1",
            callback=self.mock_callback
        )

        # Should have tx_hash and confirmed events
        self.assertEqual(len(self.callback_events), 2)
        self.assertEqual(self.callback_events[0], ("tx_hash", "test-order-1", "0x123abc"))
        self.assertEqual(self.callback_events[1], ("confirmed", "test-order-1", response))

    def test_immediate_failed(self):
        """Test transaction that is immediately failed."""
        asyncio.run(self._test_immediate_failed())

    async def _test_immediate_failed(self):
        """Async test for immediate failure."""
        response = {
            "signature": "0x456def",
            "status": -1,  # FAILED
            "message": "Insufficient funds"
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-order-2",
            callback=self.mock_callback
        )

        # Should have tx_hash and failed events
        self.assertEqual(len(self.callback_events), 2)
        self.assertEqual(self.callback_events[0], ("tx_hash", "test-order-2", "0x456def"))
        self.assertEqual(self.callback_events[1], ("failed", "test-order-2", "Insufficient funds"))

    def test_pending_then_confirmed(self):
        """Test transaction that starts pending then gets confirmed."""
        asyncio.run(self._test_pending_then_confirmed())

    async def _test_pending_then_confirmed(self):
        """Async test for pending then confirmed."""
        response = {
            "signature": "0x789ghi",
            "status": 0  # PENDING
        }

        # Mock get_transaction_status to return confirmed after 2 calls
        poll_responses = [
            {"txStatus": 0},  # Still pending
            {"txStatus": 1}   # Confirmed
        ]
        self.gateway_client.get_transaction_status = AsyncMock(side_effect=poll_responses)

        # Use shorter poll interval for testing
        self.monitor.POLL_INTERVAL = 0.1

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-order-3",
            callback=self.mock_callback
        )

        # Should have tx_hash and confirmed events
        self.assertEqual(len(self.callback_events), 2)
        self.assertEqual(self.callback_events[0], ("tx_hash", "test-order-3", "0x789ghi"))
        self.assertEqual(self.callback_events[1], ("confirmed", "test-order-3", {"txStatus": 1}))

        # Verify polling was called
        self.assertEqual(self.gateway_client.get_transaction_status.call_count, 2)

    def test_timeout(self):
        """Test transaction that times out."""
        asyncio.run(self._test_timeout())

    async def _test_timeout(self):
        """Async test for timeout."""
        response = {
            "signature": "0xabcdef",
            "status": 0  # PENDING
        }

        # Mock get_transaction_status to always return pending
        self.gateway_client.get_transaction_status = AsyncMock(
            return_value={"txStatus": 0}
        )

        # Use very short timeout for testing
        self.monitor.POLL_INTERVAL = 0.1
        self.monitor.MAX_POLL_TIME = 0.3

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-order-4",
            callback=self.mock_callback
        )

        # Should have tx_hash and failed (timeout) events
        self.assertEqual(len(self.callback_events), 2)
        self.assertEqual(self.callback_events[0], ("tx_hash", "test-order-4", "0xabcdef"))
        self.assertEqual(self.callback_events[1][0], "failed")
        self.assertEqual(self.callback_events[1][1], "test-order-4")
        self.assertIn("timed out", self.callback_events[1][2])

    def test_no_tx_hash(self):
        """Test response with no transaction hash."""
        asyncio.run(self._test_no_tx_hash())

    async def _test_no_tx_hash(self):
        """Async test for no tx hash."""
        response = {
            "status": 0  # No signature
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-order-5",
            callback=self.mock_callback
        )

        # Should have no events
        self.assertEqual(len(self.callback_events), 0)

    def test_polling_error_handling(self):
        """Test that polling continues even with errors."""
        asyncio.run(self._test_polling_error_handling())

    async def _test_polling_error_handling(self):
        """Async test for error handling during polling."""
        response = {
            "signature": "0x123456",
            "status": 0  # PENDING
        }

        # Mock get_transaction_status to throw error then return confirmed
        async def mock_poll(*args, **kwargs):
            if mock_poll.call_count == 1:
                raise Exception("Network error")
            return {"txStatus": 1}  # Confirmed

        mock_poll.call_count = 0
        self.gateway_client.get_transaction_status = AsyncMock(side_effect=mock_poll)

        # Use shorter poll interval for testing
        self.monitor.POLL_INTERVAL = 0.1

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-order-6",
            callback=self.mock_callback
        )

        # Should still get confirmed despite error
        self.assertEqual(len(self.callback_events), 2)
        self.assertEqual(self.callback_events[0], ("tx_hash", "test-order-6", "0x123456"))
        self.assertEqual(self.callback_events[1], ("confirmed", "test-order-6", {"txStatus": 1}))


if __name__ == "__main__":
    unittest.main()
