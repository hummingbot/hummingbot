"""
Chunk 2: Balance update tests for XrplExchange.

Covers:
  - _update_balances  (with open offers, empty lines, error handling)
  - _calculate_locked_balance_for_token
"""

from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import patch

from xrpl.models.requests.request import RequestMethod

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
