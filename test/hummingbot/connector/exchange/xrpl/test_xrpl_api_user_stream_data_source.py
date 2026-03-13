"""
Unit tests for XRPLAPIUserStreamDataSource.

Tests the polling-based user stream data source that periodically fetches
account state from the XRPL ledger instead of relying on WebSocket subscriptions.
"""
import asyncio
import unittest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.xrpl.xrpl_api_user_stream_data_source import XRPLAPIUserStreamDataSource
from hummingbot.connector.exchange.xrpl.xrpl_auth import XRPLAuth
from hummingbot.connector.exchange.xrpl.xrpl_worker_manager import XRPLWorkerPoolManager


class TestXRPLAPIUserStreamDataSourceInit(unittest.TestCase):
    """Tests for XRPLAPIUserStreamDataSource initialization."""

    def test_init(self):
        """Test polling data source initializes correctly."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()
        mock_worker_manager = MagicMock(spec=XRPLWorkerPoolManager)

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=mock_worker_manager,
        )

        self.assertEqual(source._auth, mock_auth)
        self.assertEqual(source._connector, mock_connector)
        self.assertEqual(source._worker_manager, mock_worker_manager)
        self.assertIsNone(source._last_ledger_index)
        self.assertEqual(source._last_recv_time, 0)

    def test_init_without_worker_manager(self):
        """Test polling data source initializes without worker manager."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=None,
        )

        self.assertIsNone(source._worker_manager)

    def test_last_recv_time_property(self):
        """Test last_recv_time property."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

        source._last_recv_time = 1000.5
        self.assertEqual(source.last_recv_time, 1000.5)

    def test_seen_tx_hashes_initialized(self):
        """Test seen tx hashes data structures are initialized."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

        self.assertIsInstance(source._seen_tx_hashes_queue, deque)
        self.assertIsInstance(source._seen_tx_hashes_set, set)
        self.assertEqual(len(source._seen_tx_hashes_queue), 0)
        self.assertEqual(len(source._seen_tx_hashes_set), 0)


class TestXRPLAPIUserStreamDataSourceIsDuplicate(unittest.TestCase):
    """Tests for _is_duplicate method."""

    def test_is_duplicate_returns_false_for_new_hash(self):
        """Test _is_duplicate returns False for new transaction hash."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

        result = source._is_duplicate("TX_HASH_NEW")

        self.assertFalse(result)
        self.assertIn("TX_HASH_NEW", source._seen_tx_hashes_set)
        self.assertIn("TX_HASH_NEW", source._seen_tx_hashes_queue)

    def test_is_duplicate_returns_true_for_seen_hash(self):
        """Test _is_duplicate returns True for already seen hash."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

        # First call adds the hash
        source._is_duplicate("TX_HASH_123")

        # Second call should return True
        result = source._is_duplicate("TX_HASH_123")

        self.assertTrue(result)

    def test_is_duplicate_prunes_old_hashes(self):
        """Test _is_duplicate prunes old hashes when max size exceeded."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

        # Set a small max size for testing
        source._seen_tx_hashes_max_size = 5

        # Add more hashes than max size
        for i in range(10):
            source._is_duplicate(f"hash_{i}")

        # Should be capped at max size
        self.assertEqual(len(source._seen_tx_hashes_set), 5)
        self.assertEqual(len(source._seen_tx_hashes_queue), 5)

        # Oldest hashes should be removed (FIFO)
        self.assertNotIn("hash_0", source._seen_tx_hashes_set)
        self.assertNotIn("hash_1", source._seen_tx_hashes_set)

        # Newest hashes should still be present
        self.assertIn("hash_9", source._seen_tx_hashes_set)
        self.assertIn("hash_8", source._seen_tx_hashes_set)


class TestXRPLAPIUserStreamDataSourceTransformEvent(unittest.TestCase):
    """Tests for _transform_to_event method."""

    def setUp(self):
        """Set up test fixtures."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()

        self.source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

    def test_transform_to_event_offer_create(self):
        """Test _transform_to_event for OfferCreate transaction."""
        tx = {
            "hash": "TX_HASH_123",
            "TransactionType": "OfferCreate",
            "Account": "rTestAccount123",
            "Sequence": 12345,
            "TakerGets": {"currency": "USD", "value": "100", "issuer": "rIssuer"},
            "TakerPays": "50000000",
            "ledger_index": 99999,
        }
        meta = {
            "AffectedNodes": [],
            "TransactionResult": "tesSUCCESS",
        }
        tx_data = {
            "tx": tx,
            "meta": meta,
            "hash": "TX_HASH_123",
            "validated": True,
        }

        event = self.source._transform_to_event(tx, meta, tx_data)

        self.assertIsNotNone(event)
        self.assertEqual(event["hash"], "TX_HASH_123")
        self.assertEqual(event["transaction"], tx)
        self.assertEqual(event["meta"], meta)
        self.assertTrue(event["validated"])

    def test_transform_to_event_offer_cancel(self):
        """Test _transform_to_event for OfferCancel transaction."""
        tx = {
            "hash": "TX_HASH_456",
            "TransactionType": "OfferCancel",
            "Account": "rTestAccount123",
            "OfferSequence": 12344,
            "ledger_index": 99999,
        }
        meta = {
            "AffectedNodes": [],
            "TransactionResult": "tesSUCCESS",
        }
        tx_data = {
            "tx": tx,
            "meta": meta,
            "hash": "TX_HASH_456",
            "validated": True,
        }

        event = self.source._transform_to_event(tx, meta, tx_data)

        self.assertIsNotNone(event)
        self.assertEqual(event["hash"], "TX_HASH_456")

    def test_transform_to_event_payment(self):
        """Test _transform_to_event for Payment transaction."""
        tx = {
            "hash": "TX_HASH_789",
            "TransactionType": "Payment",
            "Account": "rOtherAccount",
            "Destination": "rTestAccount123",
            "Amount": "1000000",
            "ledger_index": 99999,
        }
        meta = {
            "AffectedNodes": [],
            "TransactionResult": "tesSUCCESS",
        }
        tx_data = {
            "tx": tx,
            "meta": meta,
            "hash": "TX_HASH_789",
            "validated": True,
        }

        event = self.source._transform_to_event(tx, meta, tx_data)

        self.assertIsNotNone(event)
        self.assertEqual(event["hash"], "TX_HASH_789")

    def test_transform_to_event_ignores_other_tx_types(self):
        """Test _transform_to_event ignores non-relevant transaction types."""
        tx = {
            "hash": "TX_HASH_OTHER",
            "TransactionType": "TrustSet",  # Not relevant for trading
            "Account": "rTestAccount123",
        }
        meta = {
            "TransactionResult": "tesSUCCESS",
        }
        tx_data = {}

        event = self.source._transform_to_event(tx, meta, tx_data)

        self.assertIsNone(event)

    def test_transform_to_event_handles_failed_tx(self):
        """Test _transform_to_event handles failed transactions."""
        tx = {
            "hash": "TX_HASH_FAIL",
            "TransactionType": "OfferCreate",
            "Account": "rTestAccount123",
        }
        meta = {
            "TransactionResult": "tecUNFUNDED_OFFER",  # Failed
        }
        tx_data = {
            "validated": True,
        }

        # Failed transactions should still be returned for order tracking
        event = self.source._transform_to_event(tx, meta, tx_data)

        self.assertIsNotNone(event)


class TestXRPLAPIUserStreamDataSourceAsync(unittest.IsolatedAsyncioTestCase):
    """Async tests for XRPLAPIUserStreamDataSource."""

    async def test_listen_for_user_stream_cancellation(self):
        """Test listen_for_user_stream handles cancellation gracefully."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()
        mock_worker_manager = MagicMock(spec=XRPLWorkerPoolManager)

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=mock_worker_manager,
        )

        # Set ledger index so it doesn't wait forever
        source._last_ledger_index = 12345

        output_queue = asyncio.Queue()

        # Mock _poll_account_state to return empty list
        with patch.object(source, '_poll_account_state', new=AsyncMock(return_value=[])):
            with patch.object(source, 'POLL_INTERVAL', 0.05):
                task = asyncio.create_task(
                    source.listen_for_user_stream(output_queue)
                )

                # Let it run briefly
                await asyncio.sleep(0.15)

                # Cancel
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def test_listen_for_user_stream_puts_events_in_queue(self):
        """Test listen_for_user_stream puts events in output queue."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

        # Set ledger index so it doesn't wait
        source._last_ledger_index = 12345

        output_queue = asyncio.Queue()

        # Mock _poll_account_state to return one event then empty
        call_count = 0

        async def mock_poll():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [{"hash": "TX_123", "type": "test"}]
            return []

        with patch.object(source, '_poll_account_state', side_effect=mock_poll):
            with patch.object(source, 'POLL_INTERVAL', 0.05):
                task = asyncio.create_task(
                    source.listen_for_user_stream(output_queue)
                )

                # Wait for event
                try:
                    event = await asyncio.wait_for(output_queue.get(), timeout=1.0)
                    self.assertEqual(event["hash"], "TX_123")
                finally:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def test_poll_account_state_with_worker_manager(self):
        """Test _poll_account_state uses worker manager query pool."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()
        mock_worker_manager = MagicMock(spec=XRPLWorkerPoolManager)

        # Mock query pool
        mock_query_pool = MagicMock()
        mock_query_result = MagicMock()
        mock_query_result.success = True
        mock_query_result.error = None

        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.result = {
            "account": "rTestAccount123",
            "ledger_index_max": 12345,
            "transactions": [],
        }
        mock_query_result.response = mock_response

        mock_query_pool.submit = AsyncMock(return_value=mock_query_result)
        mock_worker_manager.get_query_pool.return_value = mock_query_pool

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=mock_worker_manager,
        )
        source._last_ledger_index = 12340

        await source._poll_account_state()

        # Verify query pool was called
        mock_worker_manager.get_query_pool.assert_called_once()
        mock_query_pool.submit.assert_called_once()

        # Verify it was an AccountTx request
        call_args = mock_query_pool.submit.call_args[0][0]
        self.assertEqual(call_args.account, "rTestAccount123")

    async def test_poll_account_state_processes_transactions(self):
        """Test _poll_account_state processes new transactions."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()
        mock_worker_manager = MagicMock(spec=XRPLWorkerPoolManager)

        # Mock query pool with a transaction
        mock_query_pool = MagicMock()
        mock_query_result = MagicMock()
        mock_query_result.success = True
        mock_query_result.error = None

        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.result = {
            "account": "rTestAccount123",
            "transactions": [
                {
                    "tx": {
                        "hash": "TX_HASH_123",
                        "TransactionType": "OfferCreate",
                        "Account": "rTestAccount123",
                        "ledger_index": 12350,
                    },
                    "meta": {
                        "TransactionResult": "tesSUCCESS",
                    },
                    "validated": True,
                }
            ],
        }
        mock_query_result.response = mock_response

        mock_query_pool.submit = AsyncMock(return_value=mock_query_result)
        mock_worker_manager.get_query_pool.return_value = mock_query_pool

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=mock_worker_manager,
        )
        source._last_ledger_index = 12340

        events = await source._poll_account_state()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["hash"], "TX_HASH_123")
        # Ledger index should be updated
        self.assertEqual(source._last_ledger_index, 12350)

    async def test_poll_account_state_deduplicates_transactions(self):
        """Test _poll_account_state deduplicates seen transactions."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()
        mock_worker_manager = MagicMock(spec=XRPLWorkerPoolManager)

        # Create a response with the same transaction
        transaction_data = {
            "tx": {
                "hash": "TX_HASH_DUPE",
                "TransactionType": "OfferCreate",
                "Account": "rTestAccount123",
                "ledger_index": 12350,
            },
            "meta": {"TransactionResult": "tesSUCCESS"},
            "validated": True,
        }

        mock_query_pool = MagicMock()
        mock_query_result = MagicMock()
        mock_query_result.success = True
        mock_query_result.error = None

        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.result = {
            "account": "rTestAccount123",
            "transactions": [transaction_data],
        }
        mock_query_result.response = mock_response

        mock_query_pool.submit = AsyncMock(return_value=mock_query_result)
        mock_worker_manager.get_query_pool.return_value = mock_query_pool

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=mock_worker_manager,
        )
        source._last_ledger_index = 12340

        # First poll - should return the transaction
        events1 = await source._poll_account_state()
        self.assertEqual(len(events1), 1)

        # Second poll with same transaction - should be deduplicated
        events2 = await source._poll_account_state()
        self.assertEqual(len(events2), 0)

    async def test_initialize_ledger_index(self):
        """Test _initialize_ledger_index sets the ledger index."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()
        mock_worker_manager = MagicMock(spec=XRPLWorkerPoolManager)

        # Mock query pool for ledger request
        mock_query_pool = MagicMock()
        mock_query_result = MagicMock()
        mock_query_result.success = True

        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.result = {
            "ledger_index": 99999,
        }
        mock_query_result.response = mock_response

        mock_query_pool.submit = AsyncMock(return_value=mock_query_result)
        mock_worker_manager.get_query_pool.return_value = mock_query_pool

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=mock_worker_manager,
        )

        await source._initialize_ledger_index()

        self.assertEqual(source._last_ledger_index, 99999)

    async def test_set_worker_manager(self):
        """Test set_worker_manager method."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=None,
        )

        self.assertIsNone(source._worker_manager)

        new_worker_manager = MagicMock(spec=XRPLWorkerPoolManager)
        source.set_worker_manager(new_worker_manager)

        self.assertEqual(source._worker_manager, new_worker_manager)

    async def test_reset_state(self):
        """Test reset_state clears polling state."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_connector = MagicMock()

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
        )

        # Set some state
        source._last_ledger_index = 12345
        source._seen_tx_hashes_queue.append("hash1")
        source._seen_tx_hashes_set.add("hash1")

        source.reset_state()

        self.assertIsNone(source._last_ledger_index)
        self.assertEqual(len(source._seen_tx_hashes_queue), 0)
        self.assertEqual(len(source._seen_tx_hashes_set), 0)


class TestXRPLAPIUserStreamDataSourceFallback(unittest.IsolatedAsyncioTestCase):
    """Tests for fallback behavior without worker manager."""

    async def test_poll_without_worker_manager_uses_node_pool(self):
        """Test _poll_account_state works without worker manager using node pool directly."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()

        # Mock node pool and client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.is_successful.return_value = True
        mock_response.result = {
            "account": "rTestAccount123",
            "transactions": [],
        }
        mock_client._request_impl = AsyncMock(return_value=mock_response)

        mock_node_pool = MagicMock()
        mock_node_pool.get_client = AsyncMock(return_value=mock_client)
        mock_connector._node_pool = mock_node_pool

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=None,  # No worker manager
        )
        source._last_ledger_index = 12340

        await source._poll_account_state()

        # Should have used node pool directly
        mock_node_pool.get_client.assert_called_once_with(use_burst=False)
        mock_client._request_impl.assert_called_once()

    async def test_poll_without_worker_manager_handles_keyerror(self):
        """Test _poll_account_state handles KeyError during reconnection."""
        mock_auth = MagicMock(spec=XRPLAuth)
        mock_auth.get_account.return_value = "rTestAccount123"
        mock_connector = MagicMock()

        # Mock client that raises KeyError (simulating reconnection)
        mock_client = MagicMock()
        mock_client._request_impl = AsyncMock(side_effect=KeyError("id"))

        mock_node_pool = MagicMock()
        mock_node_pool.get_client = AsyncMock(return_value=mock_client)
        mock_connector._node_pool = mock_node_pool

        source = XRPLAPIUserStreamDataSource(
            auth=mock_auth,
            connector=mock_connector,
            worker_manager=None,
        )
        source._last_ledger_index = 12340

        # Should not raise, just return empty events
        events = await source._poll_account_state()

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
