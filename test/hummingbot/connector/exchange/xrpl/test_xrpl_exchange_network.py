"""
Chunk 3 – Network & utility tests for XrplExchange.

Covers:
- start_network / stop_network / _ensure_network_started
- _init_specialized_workers
- _query_xrpl (success, failure, auto-start)
- _submit_transaction
- tx_autofill / tx_sign / tx_submit
- wait_for_final_transaction_outcome
- get_currencies_from_trading_pair
- get_token_symbol_from_all_markets
- _get_order_status_lock / _cleanup_order_status_lock
- _fetch_account_transactions
"""

import asyncio
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.asyncio.clients import XRPLRequestFailureException
from xrpl.asyncio.transaction import XRPLReliableSubmissionException
from xrpl.models import XRP, AccountInfo, IssuedCurrency, OfferCancel, Response
from xrpl.models.response import ResponseStatus, ResponseType

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import QueryResult, TransactionSubmitResult

from .test_xrpl_exchange_base import XRPLExchangeTestBase


class TestXRPLExchangeNetwork(XRPLExchangeTestBase, IsolatedAsyncioTestCase):
    """Tests for network lifecycle, query/submit, and utility methods."""

    # ------------------------------------------------------------------ #
    # _init_specialized_workers
    # ------------------------------------------------------------------ #

    def test_init_specialized_workers(self):
        """_init_specialized_workers should populate _query_pool, _verification_pool, and _tx_pool."""
        mock_manager = MagicMock()
        mock_query_pool = MagicMock()
        mock_verification_pool = MagicMock()
        mock_tx_pool = MagicMock()

        mock_manager.get_query_pool.return_value = mock_query_pool
        mock_manager.get_verification_pool.return_value = mock_verification_pool
        mock_manager.get_transaction_pool.return_value = mock_tx_pool

        self.connector._worker_manager = mock_manager
        self.connector._init_specialized_workers()

        self.assertIs(self.connector._query_pool, mock_query_pool)
        self.assertIs(self.connector._verification_pool, mock_verification_pool)
        self.assertIs(self.connector._tx_pool, mock_tx_pool)
        mock_manager.get_query_pool.assert_called_once()
        mock_manager.get_verification_pool.assert_called_once()
        mock_manager.get_transaction_pool.assert_called_once()

    # ------------------------------------------------------------------ #
    # _ensure_network_started
    # ------------------------------------------------------------------ #

    async def test_ensure_network_started_both_stopped(self):
        """When both node pool and worker manager are stopped, both should start."""
        self.connector._node_pool = MagicMock()
        self.connector._node_pool.is_running = False
        self.connector._node_pool.start = AsyncMock()
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = False
        self.connector._worker_manager.start = AsyncMock()

        await self.connector._ensure_network_started()

        self.connector._node_pool.start.assert_awaited_once()
        self.connector._worker_manager.start.assert_awaited_once()

    async def test_ensure_network_started_already_running(self):
        """When both are already running, neither start should be called."""
        self.connector._node_pool = MagicMock()
        self.connector._node_pool.is_running = True
        self.connector._node_pool.start = AsyncMock()
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = True
        self.connector._worker_manager.start = AsyncMock()

        await self.connector._ensure_network_started()

        self.connector._node_pool.start.assert_not_awaited()
        self.connector._worker_manager.start.assert_not_awaited()

    # ------------------------------------------------------------------ #
    # _query_xrpl
    # ------------------------------------------------------------------ #

    async def test_query_xrpl_success(self):
        """Successful query returns the response."""
        expected_resp = self._client_response_account_info()

        mock_pool = MagicMock()
        mock_pool.submit = AsyncMock(
            return_value=QueryResult(success=True, response=expected_resp, error=None)
        )
        self.connector._query_pool = mock_pool
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = True

        result = await self.connector._query_xrpl(AccountInfo(account="rTest"))

        self.assertEqual(result.status, ResponseStatus.SUCCESS)
        mock_pool.submit.assert_awaited_once()

    async def test_query_xrpl_failure_with_response(self):
        """Failed query with a response still returns the response."""
        err_resp = Response(
            status=ResponseStatus.ERROR,
            result={"error": "actNotFound"},
            id="test",
            type=ResponseType.RESPONSE,
        )

        mock_pool = MagicMock()
        mock_pool.submit = AsyncMock(
            return_value=QueryResult(success=False, response=err_resp, error="actNotFound")
        )
        self.connector._query_pool = mock_pool
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = True

        result = await self.connector._query_xrpl(AccountInfo(account="rTest"))
        self.assertEqual(result.status, ResponseStatus.ERROR)

    async def test_query_xrpl_failure_no_response_raises(self):
        """Failed query without a response raises Exception."""
        mock_pool = MagicMock()
        mock_pool.submit = AsyncMock(
            return_value=QueryResult(success=False, response=None, error="timeout")
        )
        self.connector._query_pool = mock_pool
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = True

        with self.assertRaises(Exception) as ctx:
            await self.connector._query_xrpl(AccountInfo(account="rTest"))
        self.assertIn("timeout", str(ctx.exception))

    async def test_query_xrpl_auto_starts_when_manager_not_running(self):
        """If worker manager is not running, _ensure_network_started is called."""
        expected_resp = self._client_response_account_info()

        mock_pool = MagicMock()
        mock_pool.submit = AsyncMock(
            return_value=QueryResult(success=True, response=expected_resp, error=None)
        )
        self.connector._query_pool = mock_pool

        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = False

        self.connector._ensure_network_started = AsyncMock()

        await self.connector._query_xrpl(AccountInfo(account="rTest"))

        self.connector._ensure_network_started.assert_awaited_once()

    # ------------------------------------------------------------------ #
    # _submit_transaction
    # ------------------------------------------------------------------ #

    async def test_submit_transaction_returns_dict(self):
        """_submit_transaction returns a backward-compatible dict."""
        signed_tx = MagicMock()
        signed_tx.sequence = 100
        signed_tx.last_ledger_sequence = 200

        result = TransactionSubmitResult(
            success=True,
            signed_tx=signed_tx,
            response=Response(status=ResponseStatus.SUCCESS, result={"engine_result": "tesSUCCESS"}),
            prelim_result="tesSUCCESS",
            exchange_order_id="100-200-HASH",
            tx_hash="HASH123",
        )

        mock_pool = MagicMock()
        mock_pool.submit_transaction = AsyncMock(return_value=result)
        self.connector._tx_pool = mock_pool

        tx = MagicMock()  # unsigned transaction
        resp = await self.connector._submit_transaction(tx)

        self.assertIsInstance(resp, dict)
        self.assertEqual(resp["prelim_result"], "tesSUCCESS")
        self.assertEqual(resp["exchange_order_id"], "100-200-HASH")
        self.assertIs(resp["signed_tx"], signed_tx)
        mock_pool.submit_transaction.assert_awaited_once()

    # ------------------------------------------------------------------ #
    # tx_submit
    # ------------------------------------------------------------------ #

    async def test_tx_submit_success(self):
        """tx_submit returns response on success."""
        mock_client = AsyncMock()
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": ["something"]},
            id="tx_submit_1234",
            type=ResponseType.RESPONSE,
        )

        some_tx = OfferCancel(
            account="r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
            offer_sequence=88824981,
        )

        resp = await self.connector.tx_submit(some_tx, mock_client)
        self.assertEqual(resp.status, ResponseStatus.SUCCESS)

    async def test_tx_submit_error_raises(self):
        """tx_submit raises XRPLRequestFailureException on error response."""
        mock_client = AsyncMock()
        mock_client._request_impl.return_value = Response(
            status=ResponseStatus.ERROR,
            result={"error": "something"},
            id="tx_submit_1234",
            type=ResponseType.RESPONSE,
        )

        some_tx = OfferCancel(
            account="r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK",  # noqa: mock
            offer_sequence=88824981,
        )

        with self.assertRaises(XRPLRequestFailureException) as ctx:
            await self.connector.tx_submit(some_tx, mock_client)
        self.assertIn("something", str(ctx.exception))

    # ------------------------------------------------------------------ #
    # tx_autofill / tx_sign
    # ------------------------------------------------------------------ #

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.autofill")
    async def test_tx_autofill(self, mock_autofill):
        """tx_autofill delegates to the autofill utility."""
        mock_tx = MagicMock()
        mock_client = MagicMock()
        mock_autofill.return_value = mock_tx

        result = await self.connector.tx_autofill(mock_tx, mock_client)

        mock_autofill.assert_called_once_with(mock_tx, mock_client, None)
        self.assertIs(result, mock_tx)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.sign")
    def test_tx_sign(self, mock_sign):
        """tx_sign delegates to the sign utility."""
        mock_tx = MagicMock()
        mock_wallet = MagicMock()
        mock_sign.return_value = mock_tx

        result = self.connector.tx_sign(mock_tx, mock_wallet)

        mock_sign.assert_called_once_with(mock_tx, mock_wallet, False)
        self.assertIs(result, mock_tx)

    # ------------------------------------------------------------------ #
    # wait_for_final_transaction_outcome
    # ------------------------------------------------------------------ #

    async def test_wait_for_final_outcome_validated_success(self):
        """Returns response when transaction is validated with tesSUCCESS."""
        mock_tx = MagicMock()
        mock_tx.get_hash.return_value = "ABCDEF1234567890"
        mock_tx.last_ledger_sequence = 1000

        ledger_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"ledger_index": 990},
        )
        tx_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"validated": True, "meta": {"TransactionResult": "tesSUCCESS"}},
        )

        call_count = 0

        async def dispatch(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            # First call is ledger, second is Tx
            if call_count % 2 == 1:
                return ledger_resp
            else:
                return tx_resp

        self.connector._query_xrpl = AsyncMock(side_effect=dispatch)

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.asyncio.sleep", new_callable=AsyncMock):
            result = await self.connector.wait_for_final_transaction_outcome(mock_tx, "tesSUCCESS", max_attempts=5)

        self.assertEqual(result.result["validated"], True)

    async def test_wait_for_final_outcome_ledger_exceeded(self):
        """Raises XRPLReliableSubmissionException when ledger sequence exceeded."""
        mock_tx = MagicMock()
        mock_tx.get_hash.return_value = "ABCDEF1234567890"
        mock_tx.last_ledger_sequence = 100

        ledger_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"ledger_index": 115},  # 115 - 100 = 15 > 10
        )

        self.connector._query_xrpl = AsyncMock(return_value=ledger_resp)

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(XRPLReliableSubmissionException):
                await self.connector.wait_for_final_transaction_outcome(mock_tx, "tesSUCCESS", max_attempts=5)

    async def test_wait_for_final_outcome_tx_not_found_then_found(self):
        """Keeps polling when txnNotFound, then succeeds on validation."""
        mock_tx = MagicMock()
        mock_tx.get_hash.return_value = "ABCDEF1234567890"
        mock_tx.last_ledger_sequence = 1000

        ledger_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"ledger_index": 990},
        )
        not_found_resp = Response(
            status=ResponseStatus.ERROR,
            result={"error": "txnNotFound"},
        )
        validated_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"validated": True, "meta": {"TransactionResult": "tesSUCCESS"}},
        )

        responses = [
            ledger_resp, not_found_resp,  # attempt 1
            ledger_resp, validated_resp,  # attempt 2
        ]
        call_idx = 0

        async def dispatch(request, priority=None, timeout=None):
            nonlocal call_idx
            resp = responses[call_idx]
            call_idx += 1
            return resp

        self.connector._query_xrpl = AsyncMock(side_effect=dispatch)

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.asyncio.sleep", new_callable=AsyncMock):
            result = await self.connector.wait_for_final_transaction_outcome(mock_tx, "tesSUCCESS", max_attempts=5)
        self.assertTrue(result.result["validated"])

    async def test_wait_for_final_outcome_validated_failure(self):
        """Raises XRPLReliableSubmissionException when tx validated but not tesSUCCESS."""
        mock_tx = MagicMock()
        mock_tx.get_hash.return_value = "ABCDEF1234567890"
        mock_tx.last_ledger_sequence = 1000

        ledger_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"ledger_index": 990},
        )
        tx_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"validated": True, "meta": {"TransactionResult": "tecUNFUNDED_OFFER"}},
        )

        call_count = 0

        async def dispatch(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                return ledger_resp
            else:
                return tx_resp

        self.connector._query_xrpl = AsyncMock(side_effect=dispatch)

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(XRPLReliableSubmissionException):
                await self.connector.wait_for_final_transaction_outcome(mock_tx, "tesSUCCESS", max_attempts=5)

    async def test_wait_for_final_outcome_timeout(self):
        """Raises TimeoutError when max attempts reached."""
        mock_tx = MagicMock()
        mock_tx.get_hash.return_value = "ABCDEF1234567890"
        mock_tx.last_ledger_sequence = 1000

        ledger_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"ledger_index": 990},
        )
        not_found_resp = Response(
            status=ResponseStatus.ERROR,
            result={"error": "txnNotFound"},
        )

        call_count = 0

        async def dispatch(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                return ledger_resp
            else:
                return not_found_resp

        self.connector._query_xrpl = AsyncMock(side_effect=dispatch)

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.asyncio.sleep", new_callable=AsyncMock):
            with self.assertRaises(TimeoutError):
                await self.connector.wait_for_final_transaction_outcome(mock_tx, "tesSUCCESS", max_attempts=2)

    # ------------------------------------------------------------------ #
    # get_currencies_from_trading_pair
    # ------------------------------------------------------------------ #

    def test_get_currencies_solo_xrp(self):
        """SOLO-XRP should return (IssuedCurrency, XRP)."""
        base_currency, quote_currency = self.connector.get_currencies_from_trading_pair("SOLO-XRP")

        self.assertIsInstance(quote_currency, XRP)
        self.assertIsInstance(base_currency, IssuedCurrency)
        self.assertEqual(base_currency.issuer, "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz")

    def test_get_currencies_solo_usd(self):
        """SOLO-USD should return (IssuedCurrency, IssuedCurrency)."""
        base_currency, quote_currency = self.connector.get_currencies_from_trading_pair("SOLO-USD")

        self.assertIsInstance(base_currency, IssuedCurrency)
        self.assertIsInstance(quote_currency, IssuedCurrency)

    def test_get_currencies_unknown_pair_raises(self):
        """Unknown trading pair should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            self.connector.get_currencies_from_trading_pair("FAKE-PAIR")
        self.assertIn("FAKE-PAIR", str(ctx.exception))

    # ------------------------------------------------------------------ #
    # get_token_symbol_from_all_markets
    # ------------------------------------------------------------------ #

    def test_get_token_symbol_found(self):
        """Known code+issuer returns the uppercase symbol."""
        result = self.connector.get_token_symbol_from_all_markets(
            "SOLO", "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz"  # noqa: mock
        )
        self.assertEqual(result, "SOLO")

    def test_get_token_symbol_not_found(self):
        """Unknown code+issuer returns None."""
        result = self.connector.get_token_symbol_from_all_markets("INVALID", "invalid_issuer")
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # _get_order_status_lock / _cleanup_order_status_lock
    # ------------------------------------------------------------------ #

    async def test_get_order_status_lock_creates_new(self):
        """First call creates a new lock."""
        lock = await self.connector._get_order_status_lock("order_1")

        self.assertIsInstance(lock, asyncio.Lock)
        self.assertIn("order_1", self.connector._order_status_locks)

    async def test_get_order_status_lock_returns_same(self):
        """Second call returns the same lock instance."""
        lock1 = await self.connector._get_order_status_lock("order_1")
        lock2 = await self.connector._get_order_status_lock("order_1")

        self.assertIs(lock1, lock2)

    async def test_cleanup_order_status_lock(self):
        """Cleanup removes the lock."""
        await self.connector._get_order_status_lock("order_1")
        self.assertIn("order_1", self.connector._order_status_locks)

        await self.connector._cleanup_order_status_lock("order_1")
        self.assertNotIn("order_1", self.connector._order_status_locks)

    async def test_cleanup_order_status_lock_missing_key(self):
        """Cleanup with a non-existent key does not raise."""
        await self.connector._cleanup_order_status_lock("nonexistent")
        # Should not raise

    # ------------------------------------------------------------------ #
    # get_order_by_sequence
    # ------------------------------------------------------------------ #

    async def test_get_order_by_sequence_found(self):
        """Returns the matching order when sequence matches."""
        from hummingbot.core.data_type.common import OrderType, TradeType
        from hummingbot.core.data_type.in_flight_order import InFlightOrder

        order = InFlightOrder(
            client_order_id="hbot",
            exchange_order_id="84437895-88954510",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1.47951609"),
            price=Decimal("0.224547537"),
            creation_timestamp=1,
        )

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {"test_order": order}

        result = self.connector.get_order_by_sequence("84437895")
        self.assertIsNotNone(result)
        self.assertEqual(result.client_order_id, "hbot")

    async def test_get_order_by_sequence_not_found(self):
        """Returns None when no order matches."""
        result = self.connector.get_order_by_sequence("100")
        self.assertIsNone(result)

    async def test_get_order_by_sequence_no_exchange_id(self):
        """Returns None when the order has no exchange_order_id."""
        from hummingbot.core.data_type.common import OrderType, TradeType
        from hummingbot.core.data_type.in_flight_order import InFlightOrder

        order = InFlightOrder(
            client_order_id="test_order",
            trading_pair="XRP_USD",
            amount=Decimal("1.47951609"),
            price=Decimal("0.224547537"),
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            exchange_order_id=None,
            creation_timestamp=1,
        )

        self.connector._order_tracker = MagicMock()
        self.connector._order_tracker.all_fillable_orders = {"test_order": order}

        result = self.connector.get_order_by_sequence("100")
        self.assertIsNone(result)

    # ------------------------------------------------------------------ #
    # _fetch_account_transactions
    # ------------------------------------------------------------------ #

    async def test_fetch_account_transactions_success(self):
        """Returns transactions from _query_xrpl response."""
        tx_list = [{"hash": "TX1"}, {"hash": "TX2"}]
        resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": tx_list},
        )

        self.connector._query_xrpl = AsyncMock(return_value=resp)

        txs = await self.connector._fetch_account_transactions(ledger_index=88824981)
        self.assertEqual(len(txs), 2)
        self.assertEqual(txs[0]["hash"], "TX1")

    async def test_fetch_account_transactions_with_pagination(self):
        """Handles marker-based pagination correctly."""
        page1_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": [{"hash": "TX1"}], "marker": "page2"},
        )
        page2_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": [{"hash": "TX2"}]},
        )

        call_count = 0

        async def dispatch(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return page1_resp
            return page2_resp

        self.connector._query_xrpl = AsyncMock(side_effect=dispatch)

        txs = await self.connector._fetch_account_transactions(ledger_index=88824981)
        self.assertEqual(len(txs), 2)

    async def test_fetch_account_transactions_error(self):
        """Returns empty list on exception."""
        self.connector._query_xrpl = AsyncMock(side_effect=Exception("Network error"))

        txs = await self.connector._fetch_account_transactions(ledger_index=88824981)
        self.assertEqual(txs, [])

    async def test_fetch_account_transactions_connection_retry(self):
        """Retries on ConnectionError, then succeeds."""
        tx_resp = Response(
            status=ResponseStatus.SUCCESS,
            result={"transactions": [{"hash": "TX1"}]},
        )

        call_count = 0

        async def dispatch(request, priority=None, timeout=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Connection lost")
            return tx_resp

        self.connector._query_xrpl = AsyncMock(side_effect=dispatch)
        self.connector._sleep = AsyncMock()

        txs = await self.connector._fetch_account_transactions(ledger_index=88824981)
        self.assertEqual(len(txs), 1)

    # ------------------------------------------------------------------ #
    # stop_network
    # ------------------------------------------------------------------ #

    async def test_stop_network_first_run_skips(self):
        """On first run, stop_network does not stop worker manager or node pool."""
        self.connector._first_run = True
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = True
        self.connector._worker_manager.stop = AsyncMock()
        self.connector._node_pool = MagicMock()
        self.connector._node_pool.is_running = True
        self.connector._node_pool.stop = AsyncMock()

        # Mock super().stop_network()
        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.ExchangePyBase.stop_network", new_callable=AsyncMock):
            await self.connector.stop_network()

        self.connector._worker_manager.stop.assert_not_awaited()
        self.connector._node_pool.stop.assert_not_awaited()
        self.assertFalse(self.connector._first_run)

    async def test_stop_network_second_run_stops_resources(self):
        """On subsequent runs, stop_network stops worker manager and node pool."""
        self.connector._first_run = False
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = True
        self.connector._worker_manager.stop = AsyncMock()
        self.connector._node_pool = MagicMock()
        self.connector._node_pool.is_running = True
        self.connector._node_pool.stop = AsyncMock()

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.ExchangePyBase.stop_network", new_callable=AsyncMock):
            await self.connector.stop_network()

        self.connector._worker_manager.stop.assert_awaited_once()
        self.connector._node_pool.stop.assert_awaited_once()

    async def test_stop_network_not_running_skips_stop(self):
        """stop_network doesn't call stop on resources that aren't running."""
        self.connector._first_run = False
        self.connector._worker_manager = MagicMock()
        self.connector._worker_manager.is_running = False
        self.connector._worker_manager.stop = AsyncMock()
        self.connector._node_pool = MagicMock()
        self.connector._node_pool.is_running = False
        self.connector._node_pool.stop = AsyncMock()

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.ExchangePyBase.stop_network", new_callable=AsyncMock):
            await self.connector.stop_network()

        self.connector._worker_manager.stop.assert_not_awaited()
        self.connector._node_pool.stop.assert_not_awaited()

    # ------------------------------------------------------------------ #
    # Property accessors (lazy init)
    # ------------------------------------------------------------------ #

    def test_tx_pool_property_lazy_init(self):
        """tx_pool property creates pool if None."""
        self.connector._tx_pool = None
        mock_manager = MagicMock()
        mock_pool = MagicMock()
        mock_manager.get_transaction_pool.return_value = mock_pool
        self.connector._worker_manager = mock_manager

        result = self.connector.tx_pool
        self.assertIs(result, mock_pool)

    def test_tx_pool_property_returns_existing(self):
        """tx_pool property returns existing pool."""
        mock_pool = MagicMock()
        self.connector._tx_pool = mock_pool

        result = self.connector.tx_pool
        self.assertIs(result, mock_pool)

    def test_query_pool_property_lazy_init(self):
        """query_pool property creates pool if None."""
        self.connector._query_pool = None
        mock_manager = MagicMock()
        mock_pool = MagicMock()
        mock_manager.get_query_pool.return_value = mock_pool
        self.connector._worker_manager = mock_manager

        result = self.connector.query_pool
        self.assertIs(result, mock_pool)

    def test_verification_pool_property_lazy_init(self):
        """verification_pool property creates pool if None."""
        self.connector._verification_pool = None
        mock_manager = MagicMock()
        mock_pool = MagicMock()
        mock_manager.get_verification_pool.return_value = mock_pool
        self.connector._worker_manager = mock_manager

        result = self.connector.verification_pool
        self.assertIs(result, mock_pool)

    # ------------------------------------------------------------------ #
    # Misc properties
    # ------------------------------------------------------------------ #

    def test_name_property(self):
        self.assertEqual(self.connector.name, CONSTANTS.EXCHANGE_NAME)

    def test_supported_order_types(self):
        from hummingbot.core.data_type.common import OrderType

        types = self.connector.supported_order_types()
        self.assertIn(OrderType.LIMIT, types)
        self.assertIn(OrderType.MARKET, types)
        self.assertIn(OrderType.LIMIT_MAKER, types)

    def test_is_cancel_request_in_exchange_synchronous(self):
        self.assertFalse(self.connector.is_cancel_request_in_exchange_synchronous)

    def test_is_request_exception_related_to_time_synchronizer(self):
        self.assertFalse(self.connector._is_request_exception_related_to_time_synchronizer(Exception()))

    def test_is_order_not_found_during_status_update(self):
        self.assertFalse(self.connector._is_order_not_found_during_status_update_error(Exception()))

    def test_is_order_not_found_during_cancelation(self):
        self.assertFalse(self.connector._is_order_not_found_during_cancelation_error(Exception()))
