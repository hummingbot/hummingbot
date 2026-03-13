"""
Chunk 7 – User Stream Event Listener Tests
============================================
Tests for:
  - _user_stream_event_listener
  - _process_market_order_transaction
  - _process_order_book_changes
"""

import unittest
from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _async_generator(items):
    for item in items:
        yield item


OUR_ACCOUNT = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock
OTHER_ACCOUNT = "rapido5rxPmP4YkMZZEeXSHqWefxHEkqv6"  # noqa: mock
SOLO_HEX = "534F4C4F00000000000000000000000000000000"  # noqa: mock
SOLO_ISSUER = "rsoLo2S1kiGeCcn6hCUXVrCpGMWLrRrLZz"  # noqa: mock


def _make_event_message(
    *,
    account: str = OUR_ACCOUNT,
    sequence: int = 84437780,
    taker_gets="502953",
    taker_pays=None,
    tx_type: str = "OfferCreate",
    tx_result: str = "tesSUCCESS",
    affected_nodes: List[Dict[str, Any]] = None,
    tx_hash: str = "86440061A351FF77F21A24ED045EE958F6256697F2628C3555AEBF29A887518C",  # noqa: mock
    tx_date: int = 772789130,
    extra_created_offer: dict = None,
) -> dict:
    """Build a minimal but realistic event message for user-stream tests."""
    if taker_pays is None:
        taker_pays = {
            "currency": SOLO_HEX,
            "issuer": SOLO_ISSUER,
            "value": "2.239836701211152",
        }

    if affected_nodes is None:
        # Minimal set – AccountRoot change for our account + RippleState for SOLO
        affected_nodes = [
            {
                "ModifiedNode": {
                    "FinalFields": {
                        "Account": OUR_ACCOUNT,
                        "Balance": "56148988",
                        "Flags": 0,
                        "OwnerCount": 3,
                        "Sequence": sequence + 1,
                    },
                    "LedgerEntryType": "AccountRoot",
                    "LedgerIndex": "2B3020738E7A44FBDE454935A38D77F12DC5A11E0FA6DAE2D9FCF4719FFAA3BC",  # noqa: mock
                    "PreviousFields": {"Balance": "56651951", "Sequence": sequence},
                }
            },
            # Counterparty offer node (partially consumed)
            {
                "ModifiedNode": {
                    "FinalFields": {
                        "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",  # noqa: mock
                        "BookDirectory": "5C8970D155D65DB8FF49B291D7EFFA4A09F9E8A68D9974B25A07F01A195F8476",  # noqa: mock
                        "BookNode": "0",
                        "Flags": 0,
                        "OwnerNode": "2",
                        "Sequence": 71762948,
                        "TakerGets": {
                            "currency": SOLO_HEX,
                            "issuer": SOLO_ISSUER,
                            "value": "42.50531785780174",
                        },
                        "TakerPays": "9497047",
                    },
                    "LedgerEntryType": "Offer",
                    "LedgerIndex": "3ABFC9B192B73ECE8FB6E2C46E49B57D4FBC4DE8806B79D913C877C44E73549E",  # noqa: mock
                    "PreviousFields": {
                        "TakerGets": {
                            "currency": SOLO_HEX,
                            "issuer": SOLO_ISSUER,
                            "value": "44.756352009",
                        },
                        "TakerPays": "10000000",
                    },
                }
            },
            # Counterparty AccountRoot
            {
                "ModifiedNode": {
                    "FinalFields": {
                        "Account": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",  # noqa: mock
                        "Balance": "251504663",
                        "Flags": 0,
                        "OwnerCount": 30,
                        "Sequence": 71762949,
                    },
                    "LedgerEntryType": "AccountRoot",
                    "LedgerIndex": "4F7BC1BE763E253402D0CA5E58E7003D326BEA2FEB5C0FEE228660F795466F6E",  # noqa: mock
                    "PreviousFields": {"Balance": "251001710"},
                }
            },
            # RippleState (counterparty SOLO)
            {
                "ModifiedNode": {
                    "FinalFields": {
                        "Balance": {
                            "currency": SOLO_HEX,
                            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                            "value": "-195.4313653751863",
                        },
                        "Flags": 2228224,
                        "HighLimit": {
                            "currency": SOLO_HEX,
                            "issuer": "rhqTdSsJAaEReRsR27YzddqyGoWTNMhEvC",  # noqa: mock
                            "value": "399134226.5095641",
                        },
                        "HighNode": "0",
                        "LowLimit": {
                            "currency": SOLO_HEX,
                            "issuer": SOLO_ISSUER,
                            "value": "0",
                        },
                        "LowNode": "36a5",
                    },
                    "LedgerEntryType": "RippleState",
                    "LedgerIndex": "9DB660A1BF3B982E5A8F4BE0BD4684FEFEBE575741928E67E4EA1DAEA02CA5A6",  # noqa: mock
                    "PreviousFields": {
                        "Balance": {
                            "currency": SOLO_HEX,
                            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                            "value": "-197.6826246297997",
                        }
                    },
                }
            },
            # RippleState (our account SOLO)
            {
                "ModifiedNode": {
                    "FinalFields": {
                        "Balance": {
                            "currency": SOLO_HEX,
                            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                            "value": "45.47502732568766",
                        },
                        "Flags": 1114112,
                        "HighLimit": {
                            "currency": SOLO_HEX,
                            "issuer": SOLO_ISSUER,
                            "value": "0",
                        },
                        "HighNode": "3799",
                        "LowLimit": {
                            "currency": SOLO_HEX,
                            "issuer": OUR_ACCOUNT,
                            "value": "1000000000",
                        },
                        "LowNode": "0",
                    },
                    "LedgerEntryType": "RippleState",
                    "LedgerIndex": "E1C84325F137AD05CB78F59968054BCBFD43CB4E70F7591B6C3C1D1C7E44C6FC",  # noqa: mock
                    "PreviousFields": {
                        "Balance": {
                            "currency": SOLO_HEX,
                            "issuer": "rrrrrrrrrrrrrrrrrrrrBZbvji",  # noqa: mock
                            "value": "43.2239931744894",
                        }
                    },
                }
            },
        ]

    if extra_created_offer is not None:
        affected_nodes = list(affected_nodes) + [extra_created_offer]

    return {
        "transaction": {
            "Account": account,
            "Fee": "10",
            "Flags": 786432,
            "LastLedgerSequence": 88954510,
            "Sequence": sequence,
            "TakerGets": taker_gets,
            "TakerPays": taker_pays,
            "TransactionType": tx_type,
            "hash": "undefined",
            "date": tx_date,
        },
        "meta": {
            "AffectedNodes": affected_nodes,
            "TransactionIndex": 3,
            "TransactionResult": tx_result,
        },
        "hash": tx_hash,
        "ledger_index": 88954492,
        "date": tx_date,
    }


def _make_created_offer_node(account, sequence, taker_gets, taker_pays):
    """Helper to build a CreatedNode for an offer placed on the book."""
    return {
        "CreatedNode": {
            "LedgerEntryType": "Offer",
            "LedgerIndex": "B817D20849E30E15F1F3C7FA45DE9B0A82F25C6B810FA06D98877140518D625B",  # noqa: mock
            "NewFields": {
                "Account": account,
                "BookDirectory": "DEC296CEB285CDF55A1036595E94AE075D0076D32D3D81BBE1F68D4B7D5016D8",  # noqa: mock
                "BookNode": "0",
                "Flags": 131072,
                "OwnerNode": "8",
                "Sequence": sequence,
                "TakerGets": taker_gets,
                "TakerPays": taker_pays,
            },
        }
    }


# =====================================================================
# Test: _process_market_order_transaction
# =====================================================================
class TestProcessMarketOrderTransaction(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    # ---- helpers ----
    def _make_market_order(self, *, client_order_id="hbot-mkt-1", sequence=84437780,
                           order_type=OrderType.MARKET, state=OrderState.OPEN,
                           amount=Decimal("2.239836701211152")):
        order = InFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=f"{sequence}-88954510-86440061",
            trading_pair=self.trading_pair,
            order_type=order_type,
            trade_type=TradeType.BUY,
            amount=amount,
            price=Decimal("0.224547537"),
            creation_timestamp=1,
            initial_state=state,
        )
        self.connector._order_tracker.start_tracking_order(order)
        return order

    # ---- tests ----

    async def test_success_filled(self):
        """Market order with tesSUCCESS → FILLED, _process_final_order_state called."""
        order = self._make_market_order()
        meta = {"TransactionResult": "tesSUCCESS"}
        transaction = {"Sequence": 84437780}
        event = {"transaction": transaction, "meta": meta}

        mock_trade_update = MagicMock()  # No spec — MagicMock(spec=TradeUpdate) is falsy
        with patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=mock_trade_update) as ptf, \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_market_order_transaction(order, transaction, meta, event)
            ptf.assert_awaited_once()
            pfos.assert_awaited_once()
            # New state should be FILLED
            call_args = pfos.call_args
            self.assertEqual(call_args[0][1], OrderState.FILLED)
            # trade_update should be passed
            self.assertIs(call_args[0][3], mock_trade_update)

    async def test_failed_transaction(self):
        """Non-tesSUCCESS → FAILED, _process_final_order_state with FAILED."""
        order = self._make_market_order()
        meta = {"TransactionResult": "tecINSUFFICIENT_FUNDS"}
        transaction = {"Sequence": 84437780}
        event = {"transaction": transaction, "meta": meta}

        with patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_market_order_transaction(order, transaction, meta, event)
            pfos.assert_awaited_once()
            self.assertEqual(pfos.call_args[0][1], OrderState.FAILED)

    async def test_not_open_early_return(self):
        """If order state is not OPEN, method returns early (no state transition)."""
        order = self._make_market_order(state=OrderState.CANCELED)
        meta = {"TransactionResult": "tesSUCCESS"}
        transaction = {"Sequence": 84437780}
        event = {"transaction": transaction, "meta": meta}

        with patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock) as ptf, \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_market_order_transaction(order, transaction, meta, event)
            ptf.assert_not_awaited()
            pfos.assert_not_awaited()

    async def test_trade_fills_returns_none(self):
        """Successful tx but process_trade_fills returns None → FILLED still proceeds, logs error."""
        order = self._make_market_order()
        meta = {"TransactionResult": "tesSUCCESS"}
        transaction = {"Sequence": 84437780}
        event = {"transaction": transaction, "meta": meta}

        with patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=None), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_market_order_transaction(order, transaction, meta, event)
            pfos.assert_awaited_once()
            self.assertEqual(pfos.call_args[0][1], OrderState.FILLED)
            # trade_update arg should be None
            self.assertIsNone(pfos.call_args[0][3])

    async def test_lock_prevents_concurrent_updates(self):
        """Lock is acquired before checking state — ensures ordering."""
        order = self._make_market_order()
        meta = {"TransactionResult": "tesSUCCESS"}
        transaction = {"Sequence": 84437780}
        event = {"transaction": transaction, "meta": meta}

        lock_acquired = False

        original_get_lock = self.connector._get_order_status_lock

        async def tracking_get_lock(client_order_id):
            nonlocal lock_acquired
            lock_acquired = True
            return await original_get_lock(client_order_id)

        with patch.object(self.connector, "_get_order_status_lock", side_effect=tracking_get_lock), \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=None), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock):
            await self.connector._process_market_order_transaction(order, transaction, meta, event)
            self.assertTrue(lock_acquired)


# =====================================================================
# Test: _process_order_book_changes
# =====================================================================
class TestProcessOrderBookChanges(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    # ---- helpers ----
    def _make_limit_order(self, *, client_order_id="hbot-limit-1", sequence=84437895,
                          state=OrderState.OPEN, amount=Decimal("1.47951609")):
        order = InFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=f"{sequence}-88954510-86440061",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=amount,
            price=Decimal("0.224547537"),
            creation_timestamp=1,
            initial_state=state,
        )
        self.connector._order_tracker.start_tracking_order(order)
        return order

    def _obc(self, *, sequence, status, taker_gets=None, taker_pays=None, account=None):
        """Build order_book_changes list for a single offer change."""
        offer_change = {"sequence": sequence, "status": status}
        if taker_gets is not None:
            offer_change["taker_gets"] = taker_gets
        if taker_pays is not None:
            offer_change["taker_pays"] = taker_pays
        return [{
            "maker_account": account or OUR_ACCOUNT,
            "offer_changes": [offer_change],
        }]

    # ---- tests: skip / early return ----

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_wrong_account_skipped(self, _get_account_mock):
        """Changes for a different account are skipped."""
        obc = self._obc(sequence=100, status="filled", account="rOtherAccount123")
        with patch.object(self.connector, "get_order_by_sequence") as gobs:
            await self.connector._process_order_book_changes(obc, {}, {})
            gobs.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_order_not_found_skipped(self, _get_account_mock):
        """If get_order_by_sequence returns None, skip."""
        obc = self._obc(sequence=999, status="filled")
        with patch.object(self.connector, "get_order_by_sequence", return_value=None):
            await self.connector._process_order_book_changes(obc, {}, {})
            # No error raised

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_pending_create_skipped(self, _get_account_mock):
        """Orders in PENDING_CREATE state are skipped."""
        order = self._make_limit_order(state=OrderState.PENDING_CREATE)
        obc = self._obc(sequence=84437895, status="filled")
        with patch.object(self.connector, "get_order_by_sequence", return_value=order):
            await self.connector._process_order_book_changes(obc, {}, {})
            # No state transition

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_already_filled_skipped(self, _get_account_mock):
        """Orders already in FILLED state should skip duplicate updates."""
        order = self._make_limit_order(state=OrderState.FILLED)
        obc = self._obc(sequence=84437895, status="filled")

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_order_book_changes(obc, {}, {})
            pfos.assert_not_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_already_canceled_skipped(self, _get_account_mock):
        """Orders already in CANCELED state should skip."""
        order = self._make_limit_order(state=OrderState.CANCELED)
        obc = self._obc(sequence=84437895, status="cancelled")

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_order_book_changes(obc, {}, {})
            pfos.assert_not_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_already_failed_skipped(self, _get_account_mock):
        """Orders already in FAILED state should skip."""
        order = self._make_limit_order(state=OrderState.FAILED)
        obc = self._obc(sequence=84437895, status="filled")

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_order_book_changes(obc, {}, {})
            pfos.assert_not_awaited()

    # ---- tests: status mappings ----

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_filled_status(self, _get_account_mock):
        """offer status 'filled' → FILLED, _process_final_order_state called."""
        order = self._make_limit_order()
        obc = self._obc(sequence=84437895, status="filled")

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=None), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_order_book_changes(obc, {}, {})
            pfos.assert_awaited_once()
            self.assertEqual(pfos.call_args[0][1], OrderState.FILLED)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_partially_filled_status(self, _get_account_mock):
        """offer status 'partially-filled' → PARTIALLY_FILLED, order update processed."""
        order = self._make_limit_order()
        obc = self._obc(sequence=84437895, status="partially-filled")

        mock_trade_update = MagicMock()  # No spec — MagicMock(spec=TradeUpdate) is falsy
        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=mock_trade_update), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou, \
             patch.object(self.connector._order_tracker, "process_trade_update") as ptu:
            await self.connector._process_order_book_changes(obc, {}, {})
            # Should call process_order_update with PARTIALLY_FILLED
            pou.assert_called_once()
            order_update_arg = pou.call_args[1]["order_update"]
            self.assertEqual(order_update_arg.new_state, OrderState.PARTIALLY_FILLED)
            # And process trade update
            ptu.assert_called_once_with(mock_trade_update)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_cancelled_status(self, _get_account_mock):
        """offer status 'cancelled' → CANCELED, _process_final_order_state called."""
        order = self._make_limit_order()
        obc = self._obc(sequence=84437895, status="cancelled")

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_order_book_changes(obc, {}, {})
            pfos.assert_awaited_once()
            self.assertEqual(pfos.call_args[0][1], OrderState.CANCELED)

    # ---- tests: "created"/"open" status with tolerance ----

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_open_status_no_change(self, _get_account_mock):
        """offer status 'created'/'open' with matching TakerGets/TakerPays → OPEN (no state change if already OPEN)."""
        order = self._make_limit_order()
        obc = self._obc(
            sequence=84437895,
            status="created",
            taker_gets={"currency": "XRP", "value": "100.0"},
            taker_pays={"currency": SOLO_HEX, "value": "50.0"},
        )
        # Transaction with matching values
        tx = {
            "TakerGets": {"currency": "XRP", "value": "100.0"},
            "TakerPays": {"currency": SOLO_HEX, "value": "50.0"},
        }

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou:
            await self.connector._process_order_book_changes(obc, tx, {})
            # State is still OPEN → same state → no process_order_update call
            pou.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_open_status_partial_fill_detected(self, _get_account_mock):
        """offer status 'created' but values differ beyond tolerance → PARTIALLY_FILLED."""
        order = self._make_limit_order()
        obc = self._obc(
            sequence=84437895,
            status="created",
            taker_gets={"currency": "XRP", "value": "50.0"},  # Half remaining
            taker_pays={"currency": SOLO_HEX, "value": "25.0"},
        )
        tx = {
            "TakerGets": {"currency": "XRP", "value": "100.0"},  # Original was 100
            "TakerPays": {"currency": SOLO_HEX, "value": "50.0"},
        }

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=None), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou:
            await self.connector._process_order_book_changes(obc, tx, {})
            pou.assert_called_once()
            order_update_arg = pou.call_args[1]["order_update"]
            self.assertEqual(order_update_arg.new_state, OrderState.PARTIALLY_FILLED)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_xrp_drops_conversion_taker_gets(self, _get_account_mock):
        """String TakerGets (XRP drops) should be converted to XRP value."""
        order = self._make_limit_order()
        obc = self._obc(
            sequence=84437895,
            status="created",
            taker_gets={"currency": "XRP", "value": "1.0"},
            taker_pays={"currency": SOLO_HEX, "value": "2.0"},
        )
        tx = {
            "TakerGets": "1000000",  # 1 XRP in drops
            "TakerPays": {"currency": SOLO_HEX, "value": "2.0"},
        }

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou:
            await self.connector._process_order_book_changes(obc, tx, {})
            # Values match after drops conversion → OPEN (no update since already OPEN)
            pou.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_xrp_drops_conversion_taker_pays(self, _get_account_mock):
        """String TakerPays (XRP drops) should be converted to XRP value."""
        order = self._make_limit_order()
        obc = self._obc(
            sequence=84437895,
            status="created",
            taker_gets={"currency": SOLO_HEX, "value": "2.0"},
            taker_pays={"currency": "XRP", "value": "1.0"},
        )
        tx = {
            "TakerGets": {"currency": SOLO_HEX, "value": "2.0"},
            "TakerPays": "1000000",  # 1 XRP in drops
        }

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou:
            await self.connector._process_order_book_changes(obc, tx, {})
            pou.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_xrp_drops_both_sides(self, _get_account_mock):
        """Both TakerGets and TakerPays as XRP drops strings."""
        order = self._make_limit_order()
        obc = self._obc(
            sequence=84437895,
            status="created",
            taker_gets={"currency": "XRP", "value": "1.0"},
            taker_pays={"currency": "XRP", "value": "2.0"},
        )
        tx = {
            "TakerGets": "1000000",
            "TakerPays": "2000000",
        }

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou:
            await self.connector._process_order_book_changes(obc, tx, {})
            pou.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_zero_tx_values_no_division_by_zero(self, _get_account_mock):
        """Zero values in transaction should not cause division errors."""
        order = self._make_limit_order()
        obc = self._obc(
            sequence=84437895,
            status="created",
            taker_gets={"currency": "XRP", "value": "100.0"},
            taker_pays={"currency": SOLO_HEX, "value": "50.0"},
        )
        tx = {
            "TakerGets": {"currency": "XRP", "value": "0"},
            "TakerPays": {"currency": SOLO_HEX, "value": "0"},
        }

        # Should not raise
        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector._order_tracker, "process_order_update"):
            await self.connector._process_order_book_changes(obc, tx, {})

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_missing_taker_gets_pays_in_offer_change(self, _get_account_mock):
        """Offer change without taker_gets/taker_pays should be handled gracefully."""
        order = self._make_limit_order()
        obc = self._obc(
            sequence=84437895,
            status="created",
            # no taker_gets, no taker_pays
        )
        tx = {
            "TakerGets": {"currency": "XRP", "value": "100.0"},
            "TakerPays": {"currency": SOLO_HEX, "value": "50.0"},
        }

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector._order_tracker, "process_order_update"):
            await self.connector._process_order_book_changes(obc, tx, {})

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_filled_with_trade_update(self, _get_account_mock):
        """Filled with a successful trade update → both trade and order processed."""
        order = self._make_limit_order()
        obc = self._obc(sequence=84437895, status="filled")

        mock_trade = MagicMock()  # No spec — MagicMock(spec=TradeUpdate) is falsy
        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=mock_trade), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_order_book_changes(obc, {}, {})
            pfos.assert_awaited_once()
            self.assertEqual(pfos.call_args[0][1], OrderState.FILLED)
            self.assertIs(pfos.call_args[0][3], mock_trade)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_partially_filled_trade_fills_none(self, _get_account_mock):
        """Partially-filled but process_trade_fills returns None → still updates order state."""
        order = self._make_limit_order()
        obc = self._obc(sequence=84437895, status="partially-filled")

        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=None), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou:
            await self.connector._process_order_book_changes(obc, {}, {})
            pou.assert_called_once()
            self.assertEqual(pou.call_args[1]["order_update"].new_state, OrderState.PARTIALLY_FILLED)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_order_disappears_after_lock(self, _get_account_mock):
        """If order is no longer found after acquiring lock, skip."""
        order = self._make_limit_order()
        obc = self._obc(sequence=84437895, status="filled")

        call_count = 0

        def side_effect(seq):
            nonlocal call_count
            call_count += 1
            # First call returns order (before lock), second call returns None (after lock)
            if call_count <= 1:
                return order
            return None

        with patch.object(self.connector, "get_order_by_sequence", side_effect=side_effect), \
             patch.object(self.connector, "_process_final_order_state", new_callable=AsyncMock) as pfos:
            await self.connector._process_order_book_changes(obc, {}, {})
            pfos.assert_not_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account", return_value=OUR_ACCOUNT)
    async def test_partially_filled_same_state_no_duplicate_update(self, _get_account_mock):
        """If order is already PARTIALLY_FILLED and gets another partial fill, state change should still happen."""
        order = self._make_limit_order(state=OrderState.PARTIALLY_FILLED)
        obc = self._obc(sequence=84437895, status="partially-filled")

        mock_trade = MagicMock()  # No spec — MagicMock(spec=TradeUpdate) is falsy
        with patch.object(self.connector, "get_order_by_sequence", return_value=order), \
             patch.object(self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=mock_trade), \
             patch.object(self.connector._order_tracker, "process_order_update") as pou, \
             patch.object(self.connector._order_tracker, "process_trade_update") as ptu:
            await self.connector._process_order_book_changes(obc, {}, {})
            # State hasn't changed (PARTIALLY_FILLED → PARTIALLY_FILLED) → no order update
            pou.assert_not_called()
            # But trade update should still be processed
            ptu.assert_called_once_with(mock_trade)


# =====================================================================
# Test: _user_stream_event_listener
# =====================================================================
class TestUserStreamEventListener(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):

    # ---- helpers ----
    def _make_order(self, *, client_order_id="hbot-1", sequence=84437780,
                    order_type=OrderType.MARKET, state=OrderState.OPEN,
                    amount=Decimal("2.239836701211152")):
        order = InFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=f"{sequence}-88954510-86440061",
            trading_pair=self.trading_pair,
            order_type=order_type,
            trade_type=TradeType.BUY,
            amount=amount,
            price=Decimal("0.224547537"),
            creation_timestamp=1,
            initial_state=state,
        )
        self.connector._order_tracker.start_tracking_order(order)
        return order

    # ---- tests ----

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_market_order_processed(self, get_account_mock):
        """Market order is dispatched to _process_market_order_transaction."""
        get_account_mock.return_value = OUR_ACCOUNT
        order = self._make_order(sequence=84437780)
        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock) as pmot, \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()
            pmot.assert_awaited_once()
            self.assertIs(pmot.call_args[0][0], order)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_limit_order_not_dispatched_to_market(self, get_account_mock):
        """Limit order should NOT trigger _process_market_order_transaction."""
        get_account_mock.return_value = OUR_ACCOUNT
        self._make_order(sequence=84437780, order_type=OrderType.LIMIT)
        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock) as pmot, \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock) as pobc:
            await self.connector._user_stream_event_listener()
            pmot.assert_not_awaited()
            pobc.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_no_transaction_skipped(self, get_account_mock):
        """Event message without 'transaction' key is skipped."""
        get_account_mock.return_value = OUR_ACCOUNT
        event = {"meta": {"TransactionResult": "tesSUCCESS"}}  # No 'transaction'

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock) as pmot, \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock) as pobc:
            await self.connector._user_stream_event_listener()
            pmot.assert_not_awaited()
            pobc.assert_not_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_no_meta_skipped(self, get_account_mock):
        """Event message without 'meta' key is skipped."""
        get_account_mock.return_value = OUR_ACCOUNT
        event = {"transaction": {"Sequence": 1, "TransactionType": "OfferCreate"}}

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock) as pmot, \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock) as pobc:
            await self.connector._user_stream_event_listener()
            pmot.assert_not_awaited()
            pobc.assert_not_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_untracked_order_skips_market_processing(self, get_account_mock):
        """If get_order_by_sequence returns None, market processing is skipped."""
        get_account_mock.return_value = OUR_ACCOUNT
        event = _make_event_message(sequence=99999)  # No tracked order with this sequence

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock) as pmot, \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock) as pobc:
            await self.connector._user_stream_event_listener()
            pmot.assert_not_awaited()
            # _process_order_book_changes is always called
            pobc.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_balance_update_xrp(self, get_account_mock):
        """Final XRP balance from event should update _account_balances and _account_available_balances."""
        get_account_mock.return_value = OUR_ACCOUNT
        self.connector._account_balances = {"XRP": Decimal("100")}
        self.connector._account_available_balances = {"XRP": Decimal("100")}

        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()

        # XRP balance should be updated from the AccountRoot FinalFields
        # Balance "56148988" drops = 56.148988 XRP
        self.assertEqual(self.connector._account_balances.get("XRP"), Decimal("56.148988"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_balance_update_token(self, get_account_mock):
        """Final token (SOLO) balance from event should update balances."""
        get_account_mock.return_value = OUR_ACCOUNT
        self.connector._account_balances = {"SOLO": Decimal("10")}
        self.connector._account_available_balances = {"SOLO": Decimal("10")}

        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()

        # SOLO balance from RippleState FinalFields: 45.47502732568766
        self.assertEqual(self.connector._account_balances.get("SOLO"), Decimal("45.47502732568766"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_balance_update_unknown_token_skipped(self, get_account_mock):
        """Token not found by get_token_symbol_from_all_markets should be skipped."""
        get_account_mock.return_value = OUR_ACCOUNT

        event = _make_event_message(sequence=84437780)

        # Force get_token_symbol_from_all_markets to return None for SOLO
        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock), \
             patch.object(self.connector, "get_token_symbol_from_all_markets", return_value=None):
            await self.connector._user_stream_event_listener()

        # SOLO should NOT be in balances (was skipped)
        self.assertNotIn("SOLO", self.connector._account_balances or {})

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_exception_in_event_processing_is_caught(self, get_account_mock):
        """Exceptions during event processing should be caught and logged (loop continues)."""
        get_account_mock.return_value = OUR_ACCOUNT

        event_bad = _make_event_message(sequence=84437780)
        event_good = _make_event_message(sequence=84437781)

        events = [event_bad, event_good]

        call_count = 0

        async def failing_then_ok(obc, tx, em):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("test error")

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator(events)), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock, side_effect=failing_then_ok), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()

        # Both events were processed (loop didn't die on first error)
        self.assertEqual(call_count, 2)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_market_order_not_open_skips_market_processing(self, get_account_mock):
        """Market order not in OPEN state should skip _process_market_order_transaction."""
        get_account_mock.return_value = OUR_ACCOUNT
        self._make_order(sequence=84437780, order_type=OrderType.MARKET, state=OrderState.FILLED)
        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock) as pmot, \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()
            pmot.assert_not_awaited()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_amm_swap_processed_as_market(self, get_account_mock):
        """AMM_SWAP order type in OPEN state should be dispatched to _process_market_order_transaction."""
        get_account_mock.return_value = OUR_ACCOUNT
        self._make_order(sequence=84437780, order_type=OrderType.AMM_SWAP)
        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock) as pmot, \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()
            pmot.assert_awaited_once()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_balance_init_from_none(self, get_account_mock):
        """If _account_balances is None, should be initialized to empty dict before update."""
        get_account_mock.return_value = OUR_ACCOUNT
        self.connector._account_balances = None
        self.connector._account_available_balances = None

        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()

        # Balances should now be set (not None)
        self.assertIsNotNone(self.connector._account_balances)
        self.assertIn("XRP", self.connector._account_balances)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_no_our_final_balances(self, get_account_mock):
        """If get_final_balances returns nothing for our account, balances are untouched."""
        get_account_mock.return_value = OUR_ACCOUNT
        self.connector._account_balances = {"XRP": Decimal("100")}

        # Event where affected nodes only reference OTHER_ACCOUNT (not OUR_ACCOUNT)
        other_only_nodes = [
            {
                "ModifiedNode": {
                    "FinalFields": {
                        "Account": OTHER_ACCOUNT,
                        "Balance": "99000000",
                        "Flags": 0,
                        "OwnerCount": 1,
                        "Sequence": 100,
                    },
                    "LedgerEntryType": "AccountRoot",
                    "LedgerIndex": "AABB00112233",
                }
            }
        ]
        event = _make_event_message(account=OTHER_ACCOUNT, sequence=84437780, affected_nodes=other_only_nodes)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()

        # XRP balance should be unchanged
        self.assertEqual(self.connector._account_balances["XRP"], Decimal("100"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_hex_currency_decoded(self, get_account_mock):
        """Hex currency code in balance should be decoded to string (e.g., SOLO hex → SOLO)."""
        get_account_mock.return_value = OUR_ACCOUNT
        self.connector._account_balances = {}
        self.connector._account_available_balances = {}

        event = _make_event_message(sequence=84437780)

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock):
            await self.connector._user_stream_event_listener()

        # The SOLO hex code should have been decoded and stored as "SOLO"
        self.assertIn("SOLO", self.connector._account_balances)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_multiple_events_processed(self, get_account_mock):
        """Multiple events in the queue should all be processed."""
        get_account_mock.return_value = OUR_ACCOUNT

        event1 = _make_event_message(sequence=84437780, tx_hash="AAA")
        event2 = _make_event_message(sequence=84437781, tx_hash="BBB")

        call_count = 0

        async def count_calls(obc, tx, em):
            nonlocal call_count
            call_count += 1

        with patch.object(self.connector, "_iter_user_event_queue", return_value=_async_generator([event1, event2])), \
             patch.object(self.connector, "_process_market_order_transaction", new_callable=AsyncMock), \
             patch.object(self.connector, "_process_order_book_changes", new_callable=AsyncMock, side_effect=count_calls):
            await self.connector._user_stream_event_listener()

        self.assertEqual(call_count, 2)


if __name__ == "__main__":
    unittest.main()
