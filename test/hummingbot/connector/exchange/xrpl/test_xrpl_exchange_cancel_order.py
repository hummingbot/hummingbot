"""
Chunk 5 – Cancel Order tests for XrplExchange.

Covers:
    - ``_place_cancel``  (success, no exchange id, temBAD_SEQUENCE, exception)
    - ``_execute_order_cancel_and_process_update``
      (OPEN→CANCELED, already filled, already canceled, partially filled then cancel,
       submission failure, verification failure, no exchange id timeout,
       temBAD_SEQUENCE fallback, race condition – filled during cancel)
    - ``cancel_all``  (delegates to super with CANCEL_ALL_TIMEOUT)
"""

import asyncio
import time
import unittest
from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.models import Response
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import TransactionSubmitResult, TransactionVerifyResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_inflight_order(
    client_order_id: str = "hbot-cancel-1",
    exchange_order_id: str | None = "12345-67890-ABCDEF",
    trading_pair: str = "SOLO-XRP",
    order_type: OrderType = OrderType.LIMIT,
    trade_type: TradeType = TradeType.BUY,
    amount: Decimal = Decimal("100"),
    price: Decimal = Decimal("0.5"),
    state: OrderState = OrderState.OPEN,
) -> InFlightOrder:
    order = InFlightOrder(
        client_order_id=client_order_id,
        exchange_order_id=exchange_order_id,
        trading_pair=trading_pair,
        order_type=order_type,
        trade_type=trade_type,
        amount=amount,
        price=price,
        creation_timestamp=time.time(),
        initial_state=state,
    )
    return order


# --------------------------------------------------------------------------- #
# Test class
# --------------------------------------------------------------------------- #


class TestXRPLExchangeCancelOrder(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):
    """Tests for _place_cancel, _execute_order_cancel_and_process_update, cancel_all."""

    # ------------------------------------------------------------------ #
    # _place_cancel
    # ------------------------------------------------------------------ #

    async def test_place_cancel_success(self):
        """Successful cancel: tx_pool returns success."""
        self._mock_tx_pool(
            success=True, sequence=12345, prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890-ABCDEF", tx_hash="CANCEL_HASH",
        )

        order = _make_inflight_order()
        result = await self.connector._place_cancel("hbot-cancel-1", tracked_order=order)

        self.assertTrue(result.success)
        self.assertEqual(result.prelim_result, "tesSUCCESS")

    async def test_place_cancel_no_exchange_order_id(self):
        """Cancel with no exchange_order_id returns failure."""
        order = _make_inflight_order(exchange_order_id=None)
        result = await self.connector._place_cancel("hbot-cancel-noid", tracked_order=order)

        self.assertFalse(result.success)
        self.assertEqual(result.error, "No exchange order ID")

    async def test_place_cancel_tem_bad_sequence(self):
        """temBAD_SEQUENCE is treated as success (offer already gone)."""
        signed_tx = MagicMock()
        signed_tx.sequence = 12345
        signed_tx.last_ledger_sequence = 67890

        submit_result = TransactionSubmitResult(
            success=True,
            signed_tx=signed_tx,
            response=Response(status=ResponseStatus.SUCCESS, result={"engine_result": "temBAD_SEQUENCE"}),
            prelim_result="temBAD_SEQUENCE",
            exchange_order_id="12345-67890-XX",
            tx_hash="BAD_SEQ_HASH",
        )
        mock_pool = MagicMock()
        mock_pool.submit_transaction = AsyncMock(return_value=submit_result)
        self.connector._tx_pool = mock_pool

        order = _make_inflight_order()
        result = await self.connector._place_cancel("hbot-cancel-bseq", tracked_order=order)

        # temBAD_SEQUENCE should be returned as success=True
        self.assertTrue(result.success)
        self.assertEqual(result.prelim_result, "temBAD_SEQUENCE")
        self.assertIsNone(result.error)

    async def test_place_cancel_submission_failure(self):
        """Submission failure returns success=False."""
        self._mock_tx_pool(success=False, prelim_result="tecUNFUNDED")

        order = _make_inflight_order()
        result = await self.connector._place_cancel("hbot-cancel-fail", tracked_order=order)

        self.assertFalse(result.success)

    async def test_place_cancel_exception(self):
        """Exception during cancel returns success=False with error message."""
        mock_pool = MagicMock()
        mock_pool.submit_transaction = AsyncMock(side_effect=RuntimeError("network error"))
        self.connector._tx_pool = mock_pool

        order = _make_inflight_order()
        result = await self.connector._place_cancel("hbot-cancel-exc", tracked_order=order)

        self.assertFalse(result.success)
        self.assertIn("network error", result.error)

    # ------------------------------------------------------------------ #
    # _execute_order_cancel_and_process_update
    # ------------------------------------------------------------------ #

    async def test_execute_cancel_open_order_success(self):
        """Cancel an OPEN order → CANCELED."""
        order = _make_inflight_order(state=OrderState.OPEN)

        # Fresh status check returns OPEN
        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.OPEN,
        )

        # _place_cancel returns success
        self._mock_tx_pool(success=True, sequence=12345, prelim_result="tesSUCCESS")

        # Verification succeeds with cancel status
        verify_response = Response(
            status=ResponseStatus.SUCCESS,
            result={
                "meta": {
                    "AffectedNodes": [],
                },
            },
        )
        verify_result = TransactionVerifyResult(
            verified=True,
            response=verify_response,
            final_result="tesSUCCESS",
        )
        mock_verify_pool = MagicMock()
        mock_verify_pool.submit_verification = AsyncMock(return_value=verify_result)
        self.connector._verification_pool = mock_verify_pool

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update
        ), patch.object(
            self.connector, "_process_final_order_state", new_callable=AsyncMock
        ) as final_mock, patch.object(
            self.connector._order_tracker, "process_order_update"
        ):
            # Mock get_order_book_changes to return empty (means cancelled)
            with patch(
                "hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes",
                return_value=[],
            ):
                result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertTrue(result)
        final_mock.assert_awaited_once()
        # Verify called with CANCELED state
        self.assertEqual(final_mock.call_args[0][1], OrderState.CANCELED)

    async def test_execute_cancel_already_filled(self):
        """If fresh status check shows FILLED, process fills instead of canceling."""
        order = _make_inflight_order(state=OrderState.OPEN)

        filled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.FILLED,
        )

        mock_trade = MagicMock()

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=filled_update
        ), patch.object(
            self.connector, "_all_trade_updates_for_order", new_callable=AsyncMock, return_value=[mock_trade]
        ), patch.object(
            self.connector, "_process_final_order_state", new_callable=AsyncMock
        ) as final_mock, patch.object(
            self.connector._order_tracker, "process_order_update"
        ):
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertFalse(result)  # Cancellation returns False when order is filled
        final_mock.assert_awaited_once()
        self.assertEqual(final_mock.call_args[0][1], OrderState.FILLED)

    async def test_execute_cancel_already_canceled(self):
        """If fresh status check shows CANCELED, process final state directly."""
        order = _make_inflight_order(state=OrderState.OPEN)

        canceled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.CANCELED,
        )

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=canceled_update
        ), patch.object(
            self.connector, "_process_final_order_state", new_callable=AsyncMock
        ) as final_mock, patch.object(
            self.connector._order_tracker, "process_order_update"
        ):
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertTrue(result)
        final_mock.assert_awaited_once()
        self.assertEqual(final_mock.call_args[0][1], OrderState.CANCELED)

    async def test_execute_cancel_already_in_final_state_not_tracked(self):
        """Order already in final state and not actively tracked → early exit."""
        order = _make_inflight_order(state=OrderState.CANCELED)

        # Order is NOT in active_orders
        with patch.object(
            self.connector._order_tracker, "process_order_update"
        ) as tracker_mock:
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertTrue(result)  # CANCELED state returns True
        tracker_mock.assert_called_once()
        update = tracker_mock.call_args[0][0]
        self.assertEqual(update.new_state, OrderState.CANCELED)

    async def test_execute_cancel_filled_final_state_not_tracked(self):
        """Order in FILLED final state and not tracked → returns False."""
        order = _make_inflight_order(state=OrderState.FILLED)

        with patch.object(
            self.connector._order_tracker, "process_order_update"
        ):
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertFalse(result)  # FILLED state returns False for cancellation

    async def test_execute_cancel_submission_failure(self):
        """Cancel submission fails → process_order_not_found + return False."""
        order = _make_inflight_order(state=OrderState.OPEN)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.OPEN,
        )

        self._mock_tx_pool(success=False, prelim_result="tecUNFUNDED")

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update
        ), patch.object(
            self.connector._order_tracker, "process_order_update"
        ), patch.object(
            self.connector._order_tracker, "process_order_not_found", new_callable=AsyncMock
        ) as not_found_mock, patch.object(
            self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock
        ):
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertFalse(result)
        not_found_mock.assert_awaited_once_with(order.client_order_id)

    async def test_execute_cancel_no_exchange_id_timeout(self):
        """Order with no exchange_order_id times out → process_order_not_found."""
        order = _make_inflight_order(exchange_order_id=None, state=OrderState.PENDING_CREATE)

        # Mock get_exchange_order_id to timeout
        with patch.object(
            order, "get_exchange_order_id", new_callable=AsyncMock, side_effect=asyncio.TimeoutError()
        ), patch.object(
            self.connector._order_tracker, "process_order_update"
        ), patch.object(
            self.connector._order_tracker, "process_order_not_found", new_callable=AsyncMock
        ) as not_found_mock, patch.object(
            self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock
        ):
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertFalse(result)
        not_found_mock.assert_awaited_once()

    async def test_execute_cancel_tem_bad_sequence_then_canceled(self):
        """temBAD_SEQUENCE during cancel → check status → CANCELED."""
        order = _make_inflight_order(state=OrderState.OPEN)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.OPEN,
        )

        # Setup temBAD_SEQUENCE submit result
        signed_tx = MagicMock()
        signed_tx.sequence = 12345
        signed_tx.last_ledger_sequence = 67890

        submit_result = TransactionSubmitResult(
            success=True,
            signed_tx=signed_tx,
            response=Response(status=ResponseStatus.SUCCESS, result={"engine_result": "temBAD_SEQUENCE"}),
            prelim_result="temBAD_SEQUENCE",
            exchange_order_id="12345-67890-ABCDEF",
            tx_hash="BAD_SEQ",
        )
        mock_pool = MagicMock()
        mock_pool.submit_transaction = AsyncMock(return_value=submit_result)
        self.connector._tx_pool = mock_pool

        canceled_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.CANCELED,
        )

        call_count = 0

        async def status_side_effect(o, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return open_update  # First call: pre-cancel check
            return canceled_update  # Second call: post temBAD_SEQUENCE check

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, side_effect=status_side_effect
        ), patch.object(
            self.connector, "_process_final_order_state", new_callable=AsyncMock
        ) as final_mock, patch.object(
            self.connector._order_tracker, "process_order_update"
        ):
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertTrue(result)
        final_mock.assert_awaited_once()
        self.assertEqual(final_mock.call_args[0][1], OrderState.CANCELED)

    async def test_execute_cancel_verification_failure(self):
        """Verification fails → process_order_not_found."""
        order = _make_inflight_order(state=OrderState.OPEN)

        open_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.OPEN,
        )

        self._mock_tx_pool(success=True, sequence=12345, prelim_result="tesSUCCESS")
        self._mock_verification_pool(verified=False, final_result="tecKILLED")

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update
        ), patch.object(
            self.connector._order_tracker, "process_order_update"
        ), patch.object(
            self.connector._order_tracker, "process_order_not_found", new_callable=AsyncMock
        ) as not_found_mock, patch.object(
            self.connector, "_cleanup_order_status_lock", new_callable=AsyncMock
        ):
            result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertFalse(result)
        not_found_mock.assert_awaited_once()

    async def test_execute_cancel_partially_filled_then_cancel(self):
        """PARTIALLY_FILLED → process fills, then proceed with cancellation."""
        order = _make_inflight_order(state=OrderState.OPEN)

        partial_update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.PARTIALLY_FILLED,
        )

        mock_trade = MagicMock()

        # After partial fill processing, the cancel submission succeeds
        self._mock_tx_pool(success=True, sequence=12345, prelim_result="tesSUCCESS")

        # Verification shows cancel succeeded (empty changes_array → cancelled)
        verify_response = Response(
            status=ResponseStatus.SUCCESS,
            result={"meta": {}},
        )
        verify_result = TransactionVerifyResult(
            verified=True,
            response=verify_response,
            final_result="tesSUCCESS",
        )
        mock_verify_pool = MagicMock()
        mock_verify_pool.submit_verification = AsyncMock(return_value=verify_result)
        self.connector._verification_pool = mock_verify_pool

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=partial_update
        ), patch.object(
            self.connector, "_all_trade_updates_for_order", new_callable=AsyncMock, return_value=[mock_trade]
        ), patch.object(
            self.connector, "_process_final_order_state", new_callable=AsyncMock
        ) as final_mock, patch.object(
            self.connector._order_tracker, "process_order_update"
        ), patch.object(
            self.connector._order_tracker, "process_trade_update"
        ):
            with patch(
                "hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes",
                return_value=[],
            ):
                result = await self.connector._execute_order_cancel_and_process_update(order)

        self.assertTrue(result)
        final_mock.assert_awaited_once()
        self.assertEqual(final_mock.call_args[0][1], OrderState.CANCELED)

    # ------------------------------------------------------------------ #
    # cancel_all
    # ------------------------------------------------------------------ #

    async def test_cancel_all_uses_constant_timeout(self):
        """cancel_all passes CANCEL_ALL_TIMEOUT to super().cancel_all()."""
        with patch(
            "hummingbot.connector.exchange.xrpl.xrpl_exchange.ExchangePyBase.cancel_all",
            new_callable=AsyncMock,
            return_value=[],
        ) as super_cancel_mock:
            result = await self.connector.cancel_all(timeout_seconds=999)

        super_cancel_mock.assert_awaited_once_with(CONSTANTS.CANCEL_ALL_TIMEOUT)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
