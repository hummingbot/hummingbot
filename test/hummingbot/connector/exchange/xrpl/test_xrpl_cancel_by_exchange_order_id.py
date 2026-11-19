"""Cancel an XRPL offer by sequence, tracked or not.

An order left behind by a crashed or archived session has no in-flight tracker
entry, so ``_place_cancel`` -- the only cancel path -- cannot reach it. The
ledger only needs the offer sequence, which is the leading field of the exchange
order id, so the same venue call works for an orphan.

Submission is not cancellation: the pool reports success for ``tesSUCCESS`` and
``terQUEUED``, and a queued transaction can still fail or expire. An orphan has no
tracker entry to notice that, so these tests pin the confirmation step too.
"""

import unittest
from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder


class TestXRPLCancelByExchangeOrderId(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):
    """``cancel_by_exchange_order_id`` must address the ledger directly."""

    def _track(self, exchange_order_id: str, client_order_id: str = "HBOT-1") -> InFlightOrder:
        """Track an offer the way the connector does after a successful place."""
        order = InFlightOrder(
            client_order_id=client_order_id,
            trading_pair="RLUSD-XRP",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("0.5"),
            creation_timestamp=1.0,
            exchange_order_id=exchange_order_id,
        )
        self.connector._order_tracker.start_tracking_order(order)
        return order

    async def test_cancels_an_untracked_offer_by_sequence(self):
        """No in-flight entry at all -- the sequence alone is enough."""
        pool = self._mock_tx_pool(success=True, prelim_result="tesSUCCESS")
        self._mock_verification_pool(verified=True)

        out = await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "106553233-1")

        self.assertEqual(out, "106553233-1")
        call = pool.submit_transaction.await_args.kwargs
        self.assertEqual(int(call["transaction"].offer_sequence), 106553233)
        self.assertEqual(call["max_retries"], CONSTANTS.CANCEL_MAX_RETRY)
        self.assertIsNone(self.connector.in_flight_orders.get("106553233-1"))

    async def test_a_tracked_order_is_reachable_too(self):
        """The same call works for an offer this process still tracks."""
        self._track("99887-1-ABCDEF")
        pool = self._mock_tx_pool(success=True)
        self._mock_verification_pool(verified=True)

        out = await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "99887-1-ABCDEF")

        self.assertEqual(out, "99887-1-ABCDEF")
        self.assertEqual(
            int(pool.submit_transaction.await_args.kwargs["transaction"].offer_sequence), 99887)
        # Tracking is not what makes it work; the venue call is the same one.
        self.assertIn("HBOT-1", self.connector.in_flight_orders)

    async def test_a_bare_sequence_is_accepted(self):
        """The id's first field is all the ledger needs."""
        self._mock_tx_pool(success=True)
        self._mock_verification_pool(verified=True)

        out = await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "106553233")
        self.assertEqual(out, "106553233")

    async def test_a_queued_cancel_is_not_reported_until_the_ledger_confirms(self):
        """``terQUEUED`` reads as success -- so the confirmation step is the guard."""
        self._mock_tx_pool(success=True, prelim_result="terQUEUED")
        verification = self._mock_verification_pool(verified=True)

        await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "106553233-1")

        verification.submit_verification.assert_awaited_once()
        kwargs = verification.submit_verification.await_args.kwargs
        self.assertEqual(kwargs["prelim_result"], "terQUEUED")

    async def test_a_submitted_cancel_that_never_lands_raises(self):
        """Submitted, queued, and then lost: the offer may still be live."""
        self._mock_tx_pool(success=True, prelim_result="terQUEUED")
        self._mock_verification_pool(verified=False, final_result="terPRE_SEQ")

        with self.assertRaises(ValueError) as ctx:
            await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "106553233-1")
        self.assertIn("not confirmed", str(ctx.exception))

    async def test_already_gone_is_not_an_error(self):
        """temBAD_SEQUENCE means the offer is already off the book."""
        self._mock_tx_pool(success=False, prelim_result="temBAD_SEQUENCE")

        out = await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "106553233-1")
        self.assertEqual(out, "106553233-1")

    async def test_a_failed_cancel_raises(self):
        self._mock_tx_pool(success=False, prelim_result="tecUNFUNDED")

        with self.assertRaises(ValueError):
            await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "106553233-1")

    async def test_a_non_sequence_id_is_rejected_before_any_submission(self):
        pool = MagicMock()
        pool.submit_transaction = AsyncMock()
        self.connector._tx_pool = pool

        with self.assertRaises(ValueError):
            await self.connector.cancel_by_exchange_order_id(
                "RLUSD-XRP", "hbot-1794307133585-8d9f6a")
        pool.submit_transaction.assert_not_awaited()

    async def test_other_connectors_say_so_explicitly(self):
        """The base contract must fail loudly rather than pretend to cancel.

        Called unbound on the real connector: ``ExchangePyBase`` is abstract and
        extends a Cython base, so ``object.__new__`` raises ``TypeError`` before
        the assertion is ever reached (review, #8542).
        """
        with self.assertRaises(NotImplementedError):
            await ExchangePyBase.cancel_by_exchange_order_id(
                self.connector, "ANY-PAIR", "123-1")
