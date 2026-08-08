"""
Chunk 2: Balance update tests for XrplExchange.

Covers:
  - _update_balances  (with open offers, empty lines, error handling)
  - _calculate_locked_balance_for_token
"""

from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

from xrpl.models.requests.request import RequestMethod

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class TestXRPLExchangeBalances(XRPLExchangeTestBase, IsolatedAsyncioTestCase):
    """Tests for balance fetching and locked-balance calculation."""

    # ------------------------------------------------------------------ #
    # _update_balances
    # ------------------------------------------------------------------ #

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_update_balances(self, get_account_mock):
        """Rewrite from monolith: test_update_balances (line 1961).

        Uses _query_xrpl mock instead of mock_client.request.
        """
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        async def _dispatch(request, priority=None, timeout=None):
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    return self._client_response_account_info()
                elif request.method == RequestMethod.ACCOUNT_OBJECTS:
                    return self._client_response_account_objects()
                elif request.method == RequestMethod.ACCOUNT_LINES:
                    return self._client_response_account_lines()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch)

        await self.connector._update_balances()

        self.assertTrue(get_account_mock.called)

        # Total balances
        self.assertEqual(self.connector._account_balances["XRP"], Decimal("57.030864"))
        self.assertEqual(self.connector._account_balances["USD"], Decimal("0.011094399237562"))
        self.assertEqual(self.connector._account_balances["SOLO"], Decimal("35.95165691730148"))

        # Available balances (total - reserves - open offer locks)
        self.assertEqual(self.connector._account_available_balances["XRP"], Decimal("53.830868"))
        self.assertEqual(self.connector._account_available_balances["USD"], Decimal("0.011094399237562"))
        self.assertEqual(
            self.connector._account_available_balances["SOLO"],
            Decimal("32.337975848655761"),
        )

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_update_balances_empty_lines(self, get_account_mock):
        """Rewrite from monolith: test_update_balances_empty_lines (line 1990).

        Account with no trust lines — only XRP balance.
        """
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        async def _dispatch(request, priority=None, timeout=None):
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    return self._client_response_account_info()
                elif request.method == RequestMethod.ACCOUNT_OBJECTS:
                    return self._client_response_account_empty_objects()
                elif request.method == RequestMethod.ACCOUNT_LINES:
                    return self._client_response_account_empty_lines()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch)

        await self.connector._update_balances()

        self.assertTrue(get_account_mock.called)

        self.assertEqual(self.connector._account_balances["XRP"], Decimal("57.030864"))
        self.assertEqual(self.connector._account_available_balances["XRP"], Decimal("56.030864"))

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_update_balances_preserves_previous_tokens_on_empty_lines(self, get_account_mock):
        """New: when lines are empty but previous balances exist, token balances are preserved."""
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        # First call: populate with real lines
        async def _dispatch_full(request, priority=None, timeout=None):
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    return self._client_response_account_info()
                elif request.method == RequestMethod.ACCOUNT_OBJECTS:
                    return self._client_response_account_objects()
                elif request.method == RequestMethod.ACCOUNT_LINES:
                    return self._client_response_account_lines()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch_full)
        await self.connector._update_balances()

        # Verify tokens are present
        self.assertIn("SOLO", self.connector._account_balances)

        # Second call: empty lines
        async def _dispatch_empty(request, priority=None, timeout=None):
            if hasattr(request, "method"):
                if request.method == RequestMethod.ACCOUNT_INFO:
                    return self._client_response_account_info()
                elif request.method == RequestMethod.ACCOUNT_OBJECTS:
                    return self._client_response_account_empty_objects()
                elif request.method == RequestMethod.ACCOUNT_LINES:
                    return self._client_response_account_empty_lines()
            raise ValueError(f"Unexpected request: {request}")

        self._mock_query_xrpl(side_effect=_dispatch_empty)
        await self.connector._update_balances()

        # XRP should be updated from latest account_info
        self.assertEqual(self.connector._account_balances["XRP"], Decimal("57.030864"))
        # Previous token balances should be preserved as fallback
        self.assertIn("SOLO", self.connector._account_balances)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    async def test_update_balances_error_handling(self, get_account_mock):
        """New: when _query_xrpl raises, the error propagates."""
        get_account_mock.return_value = "r2XdzWFVoHGfGVmXugtKhxMu3bqhsYiWK"  # noqa: mock

        async def _dispatch(request, priority=None, timeout=None):
            raise ConnectionError("Network down")

        self._mock_query_xrpl(side_effect=_dispatch)

        with self.assertRaises(ConnectionError):
            await self.connector._update_balances()

    # ------------------------------------------------------------------ #
    # _calculate_locked_balance_for_token
    # ------------------------------------------------------------------ #

    def test_calculate_locked_balance_no_orders(self):
        """New: with no active orders, locked balance is zero."""
        result = self.connector._calculate_locked_balance_for_token("SOLO")
        self.assertEqual(result, Decimal("0"))

    def test_calculate_locked_balance_sell_order(self):
        """New: sell order locks base asset."""
        order = InFlightOrder(
            client_order_id="test_sell_1",
            exchange_order_id="12345-67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("0.2"),
            creation_timestamp=1000000,
            initial_state=OrderState.OPEN,
        )
        self.connector._order_tracker._in_flight_orders["test_sell_1"] = order

        locked = self.connector._calculate_locked_balance_for_token("SOLO")
        self.assertEqual(locked, Decimal("10"))

        # Quote asset should not be locked for a sell order
        locked_xrp = self.connector._calculate_locked_balance_for_token("XRP")
        self.assertEqual(locked_xrp, Decimal("0"))

    def test_calculate_locked_balance_buy_order(self):
        """New: buy order locks quote asset (remaining_amount * price)."""
        order = InFlightOrder(
            client_order_id="test_buy_1",
            exchange_order_id="12345-67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0.2"),
            creation_timestamp=1000000,
            initial_state=OrderState.OPEN,
        )
        self.connector._order_tracker._in_flight_orders["test_buy_1"] = order

        locked_xrp = self.connector._calculate_locked_balance_for_token("XRP")
        self.assertEqual(locked_xrp, Decimal("20"))  # 100 * 0.2

        # Base asset should not be locked for a buy order
        locked_solo = self.connector._calculate_locked_balance_for_token("SOLO")
        self.assertEqual(locked_solo, Decimal("0"))

    def test_calculate_locked_balance_partially_filled(self):
        """New: partially filled order only locks remaining amount."""
        order = InFlightOrder(
            client_order_id="test_sell_partial",
            exchange_order_id="12345-67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("0.2"),
            creation_timestamp=1000000,
            initial_state=OrderState.PARTIALLY_FILLED,
        )
        order.executed_amount_base = Decimal("4")
        self.connector._order_tracker._in_flight_orders["test_sell_partial"] = order

        locked = self.connector._calculate_locked_balance_for_token("SOLO")
        self.assertEqual(locked, Decimal("6"))  # 10 - 4

    def test_calculate_locked_balance_market_order_skipped(self):
        """New: market orders (price=None) are skipped."""
        order = InFlightOrder(
            client_order_id="test_market",
            exchange_order_id="12345-67890",
            trading_pair=self.trading_pair,
            order_type=OrderType.MARKET,
            trade_type=TradeType.BUY,
            amount=Decimal("100"),
            price=Decimal("0"),
            creation_timestamp=1000000,
            initial_state=OrderState.OPEN,
        )
        # Set price to None to simulate market order
        order.price = Decimal("0")
        self.connector._order_tracker._in_flight_orders["test_market"] = order

        # Even though order exists, locked balance should be 0 because price is 0
        # (remaining * 0 = 0 for buy order on XRP)
        locked = self.connector._calculate_locked_balance_for_token("XRP")
        self.assertEqual(locked, Decimal("0"))

    def test_calculate_locked_balance_multiple_orders(self):
        """New: multiple orders accumulate locked balances."""
        order1 = InFlightOrder(
            client_order_id="sell_1",
            exchange_order_id="111-222",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("0.2"),
            creation_timestamp=1000000,
            initial_state=OrderState.OPEN,
        )
        order2 = InFlightOrder(
            client_order_id="sell_2",
            exchange_order_id="333-444",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("5"),
            price=Decimal("0.3"),
            creation_timestamp=1000001,
            initial_state=OrderState.OPEN,
        )
        self.connector._order_tracker._in_flight_orders["sell_1"] = order1
        self.connector._order_tracker._in_flight_orders["sell_2"] = order2

        locked = self.connector._calculate_locked_balance_for_token("SOLO")
        self.assertEqual(locked, Decimal("15"))  # 10 + 5

    def test_calculate_locked_balance_fully_filled_ignored(self):
        """New: fully filled orders (remaining <= 0) are not counted."""
        order = InFlightOrder(
            client_order_id="sell_filled",
            exchange_order_id="555-666",
            trading_pair=self.trading_pair,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.SELL,
            amount=Decimal("10"),
            price=Decimal("0.2"),
            creation_timestamp=1000000,
            initial_state=OrderState.OPEN,
        )
        order.executed_amount_base = Decimal("10")
        self.connector._order_tracker._in_flight_orders["sell_filled"] = order

        locked = self.connector._calculate_locked_balance_for_token("SOLO")
        self.assertEqual(locked, Decimal("0"))


class TestXRPLBalanceSnapshotIsOneMoment(XRPLExchangeTestBase, IsolatedAsyncioTestCase):
    """XRP and the token balances must describe the SAME ledger, or the portfolio is fiction.

    XRPL settles atomically, so no real trade can move one currency without moving another — yet
    a balance refresh built from three independent queries can straddle a ledger close and read
    the account at two moments, printing a gain or loss that never happened and undoing it on the
    next tick. Ledgers close every ~4s and the connector spreads these requests across a pool of
    nodes at differing validation heights, so straddling a close is routine, not exotic.

    The failure is silent by construction: every individual response is correct and validated.
    Only their combination is wrong, so nothing errors and the number merely lies.
    """

    def setUp(self):
        super().setUp()
        self.connector._balances_ledger_index = None

    def _resp(self, ledger_index, xrp_drops="30000000", token="20"):
        r = MagicMock()
        r.result = {"ledger_index": ledger_index, "validated": True,
                    "account_data": {"Balance": xrp_drops},
                    "account_objects": [],
                    "lines": [{"currency": "USD", "account": "r_issuer", "balance": token}]}
        return r

    async def test_agreeing_ledgers_are_read_once(self):
        """The common case must not pay for the rare one."""
        calls = []

        async def q(req, **kw):
            calls.append(getattr(req, "ledger_index", None))
            return self._resp(900)

        self.connector._query_xrpl = q
        await self.connector._update_balances()
        self.assertEqual(3, len(calls), "one agreeing snapshot needs no re-read")

    async def test_a_straddled_close_is_detected_and_re_read(self):
        """Two responses at ledger N and one at N+1 — the exact shape of a phantom loss."""
        seq = []

        async def q(req, **kw):
            idx = getattr(req, "ledger_index", None)
            seq.append(idx)
            if idx == "validated":
                # first round straddles a close
                return self._resp(900 if len(seq) < 3 else 901)
            return self._resp(idx)

        self.connector._query_xrpl = q
        await self.connector._update_balances()
        self.assertEqual(6, len(seq), "a straddle must trigger exactly one pinned re-read")
        self.assertEqual([901, 901, 901], seq[3:], "the re-read must pin an explicit integer")

    async def test_the_re_read_pins_the_newest_ledger(self):
        """Behind one balancer hostname sit many backends; the oldest seen may be a laggard's
        hour-old view, so following it would follow the laggard rather than the chain."""
        seq = []

        async def q(req, **kw):
            idx = getattr(req, "ledger_index", None)
            seq.append(idx)
            if idx == "validated":
                return self._resp(905 if len(seq) == 1 else 904)
            return self._resp(idx)

        self.connector._query_xrpl = q
        await self.connector._update_balances()
        self.assertEqual(905, seq[3], "pin the newest seen, not the oldest")

    async def test_an_incomplete_re_read_keeps_the_data_and_warns(self):
        """Losing the snapshot entirely would be worse than a skewed one — but not silently."""
        seq = []

        async def q(req, **kw):
            idx = getattr(req, "ledger_index", None)
            seq.append(idx)
            if idx != "validated":
                return None            # pinned re-read fails
            return self._resp(900 if len(seq) < 3 else 901)

        self.connector._query_xrpl = q
        with self.assertLogs(level="WARNING") as cm:
            await self.connector._update_balances()
        self.assertTrue(any("skewed snapshot" in m for m in cm.output),
                        "a fallback to skewed data has to announce itself")
        self.assertIn("XRP", self.connector._account_balances)

    async def test_a_response_without_a_ledger_index_does_not_trigger_a_re_read(self):
        """Missing metadata is ignorance, not disagreement; re-reading on it would loop forever."""
        seq = []

        async def q(req, **kw):
            seq.append(getattr(req, "ledger_index", None))
            r = self._resp(900)
            if len(seq) == 2:
                r.result.pop("ledger_index")
            return r

        self.connector._query_xrpl = q
        await self.connector._update_balances()
        self.assertEqual(3, len(seq))

    def test_index_parsing_survives_junk(self):
        r = MagicMock()
        r.result = {"ledger_index": "not-a-number"}
        ok = MagicMock()
        ok.result = {"ledger_index": 12}
        self.assertEqual([12], self.connector._snapshot_ledger_indexes([r, ok, None]))

    async def test_an_incomplete_snapshot_writes_nothing(self):
        """A node that cannot serve the ledger answers with an error RESPONSE, not None.

        A None-check waves it through, and the balance built from it is zero — indistinguishable,
        to every strategy reading it, from an account that is actually empty.
        """
        async def q(req, **kw):
            r = MagicMock()
            r.result = {"error": "lgrNotFound", "ledger_index": 900}
            return r

        self.connector._query_xrpl = q
        with self.assertLogs(level="WARNING") as cm:
            await self.connector._update_balances()
        self.assertTrue(any("Incomplete account snapshot" in m for m in cm.output))
        self.assertNotIn("XRP", self.connector._account_balances,
                         "a failed read must not masquerade as a zero balance")

    async def test_a_snapshot_from_a_laggard_ledger_is_skipped(self):
        """Balances only move forward in time; an hour-old read can only undo a correct value."""
        async def q(req, **kw):
            return self._resp(900)

        self.connector._query_xrpl = q
        self.connector._balances_ledger_index = 900 + CONSTANTS.SNAPSHOT_MAX_LAG_LEDGERS + 1
        with self.assertLogs(level="WARNING") as cm:
            await self.connector._update_balances()
        self.assertTrue(any("Skipping balance snapshot" in m for m in cm.output))
        self.assertNotIn("XRP", self.connector._account_balances)

    async def test_ordinary_skew_within_the_tolerance_is_accepted(self):
        """The pool's nodes legitimately sit a few ledgers apart; only the outlier is refused."""
        async def q(req, **kw):
            return self._resp(900)

        self.connector._query_xrpl = q
        self.connector._balances_ledger_index = 900 + CONSTANTS.SNAPSHOT_MAX_LAG_LEDGERS
        await self.connector._update_balances()
        self.assertIn("XRP", self.connector._account_balances)
        self.assertEqual(900 + CONSTANTS.SNAPSHOT_MAX_LAG_LEDGERS,
                         self.connector._balances_ledger_index,
                         "the held index must never move backwards")

    async def test_a_malformed_trustline_currency_does_not_freeze_every_balance(self):
        """bytes.fromhex raises plain ValueError; only UnicodeDecodeError was caught.

        The uncaught kind escaped and aborted the whole update — silently, because the previous
        numbers stay in place and nothing distinguishes them from fresh ones.
        """
        async def q(req, **kw):
            r = self._resp(900)
            r.result["lines"] = [{"currency": "NOTHEXAT", "account": "r_issuer", "balance": "5"}]
            return r

        self.connector._query_xrpl = q
        await self.connector._update_balances()   # must not raise
        self.assertIn("XRP", self.connector._account_balances)
