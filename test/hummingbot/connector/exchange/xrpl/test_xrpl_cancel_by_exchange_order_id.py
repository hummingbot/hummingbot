"""Cancel an XRPL offer by sequence, tracked or not.

An order left behind by a crashed or archived session has no in-flight tracker
entry, so ``_place_cancel`` -- the only cancel path -- cannot reach it. The
ledger only needs the offer sequence, which is the leading field of the
exchange order id, so the same venue call works for an orphan.
"""

import unittest
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.connector.exchange_py_base import ExchangePyBase


class TestXRPLCancelByExchangeOrderId(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):
    """``cancel_by_exchange_order_id`` must address the ledger directly."""

    async def test_cancels_an_untracked_offer_by_sequence(self):
        """No in-flight entry at all -- the sequence alone is enough."""
        pool = self._mock_tx_pool(success=True, prelim_result="tesSUCCESS")

        out = await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "106553233-1")

        self.assertEqual(out, "106553233-1")
        call = pool.submit_transaction.await_args.kwargs
        self.assertEqual(int(call["transaction"].offer_sequence), 106553233)
        self.assertEqual(call["max_retries"], CONSTANTS.CANCEL_MAX_RETRY)
        self.assertIsNone(self.connector.in_flight_orders.get("106553233-1"))

    async def test_a_tracked_order_is_reachable_too(self):
        """The same call works for an offer this process still tracks."""
        pool = self._mock_tx_pool(success=True)
        out = await self.connector.cancel_by_exchange_order_id("RLUSD-XRP", "99887-1")
        self.assertEqual(out, "99887-1")
        self.assertEqual(
            int(pool.submit_transaction.await_args.kwargs["transaction"].offer_sequence), 99887)

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
        """The base contract must fail loudly rather than pretend to cancel."""
        base = object.__new__(ExchangePyBase)
        with self.assertRaises(NotImplementedError):
            await base.cancel_by_exchange_order_id("ANY-PAIR", "123-1")
