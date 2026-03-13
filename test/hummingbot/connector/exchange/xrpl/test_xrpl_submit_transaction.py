"""
Tests for XRPL transaction submission functionality.
Tests the _submit_transaction method which uses the transaction worker pool.
"""
from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from xrpl.models import Response, Transaction
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl.xrpl_exchange import XrplExchange
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import TransactionSubmitResult


class TestXRPLSubmitTransaction(IsolatedAsyncioTestCase):
    """Tests for the XrplExchange._submit_transaction method."""

    def setUp(self) -> None:
        super().setUp()
        self.exchange = XrplExchange(
            xrpl_secret_key="",
            wss_node_urls=["wss://sample.com"],
            max_request_per_minute=100,
            trading_pairs=["SOLO-XRP"],
            trading_required=False,
        )

    async def test_submit_transaction_success(self):
        """Test successful transaction submission using tx_pool."""
        # Setup transaction mock
        mock_transaction = MagicMock(spec=Transaction)
        mock_signed_tx = MagicMock(spec=Transaction)

        # Setup successful response
        mock_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "ledger_index": 99999221,
                "validated": True,
                "meta": {
                    "TransactionResult": "tesSUCCESS",
                },
            },
        )

        # Create a successful TransactionSubmitResult
        submit_result = TransactionSubmitResult(
            success=True,
            signed_tx=mock_signed_tx,
            response=mock_response,
            prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890",
            error=None,
            tx_hash="ABCD1234",
        )

        # Mock the tx_pool
        mock_tx_pool = MagicMock()
        mock_tx_pool.submit_transaction = AsyncMock(return_value=submit_result)
        self.exchange._tx_pool = mock_tx_pool

        # Execute the method
        result = await self.exchange._submit_transaction(mock_transaction)

        # Verify results
        self.assertEqual(result["signed_tx"], mock_signed_tx)
        self.assertEqual(result["response"], mock_response)
        self.assertEqual(result["prelim_result"], "tesSUCCESS")
        self.assertEqual(result["exchange_order_id"], "12345-67890")

        # Verify tx_pool was called correctly
        mock_tx_pool.submit_transaction.assert_awaited_once_with(
            transaction=mock_transaction,
            fail_hard=True,
            max_retries=3,
        )

    async def test_submit_transaction_with_fail_hard_false(self):
        """Test transaction submission with fail_hard=False."""
        mock_transaction = MagicMock(spec=Transaction)
        mock_signed_tx = MagicMock(spec=Transaction)

        submit_result = TransactionSubmitResult(
            success=True,
            signed_tx=mock_signed_tx,
            response=None,
            prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890",
        )

        mock_tx_pool = MagicMock()
        mock_tx_pool.submit_transaction = AsyncMock(return_value=submit_result)
        self.exchange._tx_pool = mock_tx_pool

        # Execute with fail_hard=False
        result = await self.exchange._submit_transaction(mock_transaction, fail_hard=False)

        # Verify tx_pool was called with fail_hard=False
        mock_tx_pool.submit_transaction.assert_awaited_once_with(
            transaction=mock_transaction,
            fail_hard=False,
            max_retries=3,
        )

        self.assertEqual(result["prelim_result"], "tesSUCCESS")

    async def test_submit_transaction_queued(self):
        """Test transaction submission that gets queued."""
        mock_transaction = MagicMock(spec=Transaction)
        mock_signed_tx = MagicMock(spec=Transaction)

        # Create a queued TransactionSubmitResult
        submit_result = TransactionSubmitResult(
            success=True,
            signed_tx=mock_signed_tx,
            response=None,
            prelim_result="terQUEUED",
            exchange_order_id="12345-67890",
        )

        mock_tx_pool = MagicMock()
        mock_tx_pool.submit_transaction = AsyncMock(return_value=submit_result)
        self.exchange._tx_pool = mock_tx_pool

        result = await self.exchange._submit_transaction(mock_transaction)

        self.assertEqual(result["prelim_result"], "terQUEUED")
        self.assertTrue(submit_result.is_queued)
        self.assertTrue(submit_result.is_accepted)

    async def test_submit_transaction_error_result(self):
        """Test transaction submission that returns an error result."""
        mock_transaction = MagicMock(spec=Transaction)

        # Create a failed TransactionSubmitResult
        submit_result = TransactionSubmitResult(
            success=False,
            signed_tx=None,
            response=None,
            prelim_result="tecNO_DST",
            exchange_order_id=None,
            error="Destination account does not exist",
        )

        mock_tx_pool = MagicMock()
        mock_tx_pool.submit_transaction = AsyncMock(return_value=submit_result)
        self.exchange._tx_pool = mock_tx_pool

        result = await self.exchange._submit_transaction(mock_transaction)

        # The method returns the result dict even on failure
        # Caller is responsible for checking success
        self.assertIsNone(result["signed_tx"])
        self.assertEqual(result["prelim_result"], "tecNO_DST")

    async def test_submit_transaction_returns_correct_dict_structure(self):
        """Test that _submit_transaction returns the expected dict structure."""
        mock_transaction = MagicMock(spec=Transaction)
        mock_signed_tx = MagicMock(spec=Transaction)
        mock_response = MagicMock(spec=Response)

        submit_result = TransactionSubmitResult(
            success=True,
            signed_tx=mock_signed_tx,
            response=mock_response,
            prelim_result="tesSUCCESS",
            exchange_order_id="order-123",
        )

        mock_tx_pool = MagicMock()
        mock_tx_pool.submit_transaction = AsyncMock(return_value=submit_result)
        self.exchange._tx_pool = mock_tx_pool

        result = await self.exchange._submit_transaction(mock_transaction)

        # Verify the result has exactly the expected keys
        expected_keys = {"signed_tx", "response", "prelim_result", "exchange_order_id"}
        self.assertEqual(set(result.keys()), expected_keys)


class TestTransactionSubmitResult(IsolatedAsyncioTestCase):
    """Tests for TransactionSubmitResult dataclass."""

    def test_is_queued_true(self):
        """Test is_queued property returns True for terQUEUED."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="terQUEUED",
        )
        self.assertTrue(result.is_queued)

    def test_is_queued_false(self):
        """Test is_queued property returns False for non-queued results."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="tesSUCCESS",
        )
        self.assertFalse(result.is_queued)

    def test_is_accepted_success(self):
        """Test is_accepted property returns True for tesSUCCESS."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="tesSUCCESS",
        )
        self.assertTrue(result.is_accepted)

    def test_is_accepted_queued(self):
        """Test is_accepted property returns True for terQUEUED."""
        result = TransactionSubmitResult(
            success=True,
            prelim_result="terQUEUED",
        )
        self.assertTrue(result.is_accepted)

    def test_is_accepted_false(self):
        """Test is_accepted property returns False for error results."""
        result = TransactionSubmitResult(
            success=False,
            prelim_result="tecNO_DST",
        )
        self.assertFalse(result.is_accepted)
