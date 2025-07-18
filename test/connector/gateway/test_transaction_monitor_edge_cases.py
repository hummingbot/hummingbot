"""
Edge case tests for TransactionMonitor.
"""
import asyncio
import unittest
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.gateway.core.transaction_monitor import TransactionMonitor


class TestTransactionMonitorEdgeCases(unittest.TestCase):
    """Test edge cases for TransactionMonitor."""

    def setUp(self):
        """Set up test fixtures."""
        self.gateway_client = MagicMock()
        self.monitor = TransactionMonitor(self.gateway_client)
        self.callback_events: List[tuple] = []

    def mock_callback(self, event_type: str, order_id: str, data: Any):
        """Mock callback to track events."""
        self.callback_events.append((event_type, order_id, data))

    def test_empty_response(self):
        """Test handling of empty response."""
        asyncio.run(self._test_empty_response())

    async def _test_empty_response(self):
        """Async test for empty response."""
        response = {}  # Empty response

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-empty",
            callback=self.mock_callback
        )

        # Should not crash, no events
        self.assertEqual(len(self.callback_events), 0)

    def test_invalid_status_values(self):
        """Test handling of invalid status values."""
        asyncio.run(self._test_invalid_status_values())

    async def _test_invalid_status_values(self):
        """Async test for invalid status values."""
        # Test with string status
        response = {
            "signature": "0x123",
            "status": "pending"  # String instead of int
        }

        # Should treat as pending (0)
        self.gateway_client.get_transaction_status = AsyncMock(
            return_value={"txStatus": 1}
        )
        self.monitor.POLL_INTERVAL = 0.1
        self.monitor.MAX_POLL_TIME = 0.3

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-string-status",
            callback=self.mock_callback
        )

        # Should poll and eventually confirm
        self.assertEqual(self.gateway_client.get_transaction_status.call_count, 1)

    def test_null_tx_hash(self):
        """Test handling of null transaction hash."""
        asyncio.run(self._test_null_tx_hash())

    async def _test_null_tx_hash(self):
        """Async test for null tx hash."""
        response = {
            "signature": None,
            "status": 0
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-null-hash",
            callback=self.mock_callback
        )

        # Should exit early
        self.assertEqual(len(self.callback_events), 0)

    def test_very_long_tx_hash(self):
        """Test handling of unusually long transaction hash."""
        asyncio.run(self._test_very_long_tx_hash())

    async def _test_very_long_tx_hash(self):
        """Async test for long tx hash."""
        long_hash = "0x" + "a" * 1000  # Very long hash
        response = {
            "signature": long_hash,
            "status": 1
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-long-hash",
            callback=self.mock_callback
        )

        # Should work normally
        self.assertEqual(len(self.callback_events), 2)
        self.assertEqual(self.callback_events[0], ("tx_hash", "test-long-hash", long_hash))

    def test_rapid_status_changes(self):
        """Test rapid status changes during polling."""
        asyncio.run(self._test_rapid_status_changes())

    async def _test_rapid_status_changes(self):
        """Async test for rapid status changes."""
        response = {
            "signature": "0xrapid",
            "status": 0
        }

        # Mock rapidly changing statuses
        poll_responses = [
            {"txStatus": 0},   # Pending
            {"txStatus": -1},  # Failed
            {"txStatus": 1},   # Should not reach this
        ]
        self.gateway_client.get_transaction_status = AsyncMock(side_effect=poll_responses)

        self.monitor.POLL_INTERVAL = 0.1

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-rapid",
            callback=self.mock_callback
        )

        # Should stop at first terminal status (failed)
        self.assertEqual(self.gateway_client.get_transaction_status.call_count, 2)
        self.assertEqual(self.callback_events[-1][0], "failed")

    def test_network_timeout_during_poll(self):
        """Test network timeout during polling."""
        asyncio.run(self._test_network_timeout_during_poll())

    async def _test_network_timeout_during_poll(self):
        """Async test for network timeout."""
        response = {
            "signature": "0xtimeout",
            "status": 0
        }

        # Mock timeouts then success
        async def mock_poll(*args, **kwargs):
            mock_poll.call_count += 1
            if mock_poll.call_count <= 2:
                raise asyncio.TimeoutError("Network timeout")
            return {"txStatus": 1}

        mock_poll.call_count = 0
        self.gateway_client.get_transaction_status = mock_poll

        self.monitor.POLL_INTERVAL = 0.1
        self.monitor.MAX_POLL_TIME = 0.5

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-network-timeout",
            callback=self.mock_callback
        )

        # Should eventually succeed despite timeouts
        self.assertEqual(self.callback_events[-1][0], "confirmed")

    def test_malformed_poll_response(self):
        """Test handling of malformed poll responses."""
        asyncio.run(self._test_malformed_poll_response())

    async def _test_malformed_poll_response(self):
        """Async test for malformed responses."""
        response = {
            "signature": "0xmalformed",
            "status": 0
        }

        # Mock various malformed responses
        poll_responses = [
            None,  # Null response
            {},    # Empty response
            {"not_status": 1},  # Missing status field
            {"txStatus": 1}  # Finally valid
        ]
        self.gateway_client.get_transaction_status = AsyncMock(side_effect=poll_responses)

        self.monitor.POLL_INTERVAL = 0.1

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-malformed",
            callback=self.mock_callback
        )

        # Should handle malformed responses gracefully
        self.assertEqual(self.gateway_client.get_transaction_status.call_count, 4)
        self.assertEqual(self.callback_events[-1], ("confirmed", "test-malformed", {"txStatus": 1}))

    def test_zero_poll_interval(self):
        """Test with zero poll interval (edge case)."""
        asyncio.run(self._test_zero_poll_interval())

    async def _test_zero_poll_interval(self):
        """Async test for zero poll interval."""
        response = {
            "signature": "0xzero",
            "status": 0
        }

        self.gateway_client.get_transaction_status = AsyncMock(
            return_value={"txStatus": 1}
        )

        # Set poll interval to 0
        self.monitor.POLL_INTERVAL = 0
        self.monitor.MAX_POLL_TIME = 0.1

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-zero-interval",
            callback=self.mock_callback
        )

        # Should still work
        self.assertEqual(self.callback_events[-1][0], "confirmed")

    def test_concurrent_same_tx_hash(self):
        """Test monitoring same transaction hash concurrently."""
        asyncio.run(self._test_concurrent_same_tx_hash())

    async def _test_concurrent_same_tx_hash(self):
        """Async test for concurrent monitoring of same tx."""
        response = {
            "signature": "0xduplicate",
            "status": 0
        }

        # Track poll count
        poll_count = 0

        async def mock_poll(*args, **kwargs):
            nonlocal poll_count
            poll_count += 1
            if poll_count >= 2:
                return {"txStatus": 1}
            return {"txStatus": 0}

        self.gateway_client.get_transaction_status = mock_poll
        self.monitor.POLL_INTERVAL = 0.1

        # Start two monitors for same transaction
        task1 = self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="order-1",
            callback=self.mock_callback
        )

        task2 = self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="order-2",
            callback=self.mock_callback
        )

        await asyncio.gather(task1, task2)

        # Both should complete successfully
        confirmed_events = [e for e in self.callback_events if e[0] == "confirmed"]
        self.assertEqual(len(confirmed_events), 2)
        self.assertEqual({e[1] for e in confirmed_events}, {"order-1", "order-2"})

    def test_unicode_in_error_message(self):
        """Test handling of unicode in error messages."""
        asyncio.run(self._test_unicode_in_error_message())

    async def _test_unicode_in_error_message(self):
        """Async test for unicode error messages."""
        response = {
            "signature": "0xunicode",
            "status": -1,
            "message": "Transaction failed: 🚫 Insufficient funds 💰"
        }

        await self.monitor.monitor_transaction(
            response=response,
            chain="ethereum",
            network="mainnet",
            order_id="test-unicode",
            callback=self.mock_callback
        )

        # Should handle unicode gracefully
        self.assertEqual(len(self.callback_events), 2)
        self.assertEqual(self.callback_events[1][0], "failed")
        self.assertIn("🚫", self.callback_events[1][2])


if __name__ == "__main__":
    unittest.main()
