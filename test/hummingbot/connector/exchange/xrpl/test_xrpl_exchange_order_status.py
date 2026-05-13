"""
Chunk 6 – Order Status Tests

Covers:
  - _request_order_status (limit order statuses: filled, partially-filled,
    cancelled, created, created-with-token-fill, no-offer-with-balance-change,
    no-offer-no-balance-change, market order success/failure, pending timeout,
    exchange-id timeout, creation_tx_resp shortcut, PENDING_CREATE within timeout)
  - _update_orders_with_error_handler (skip final-state orders, periodic
    update with trade fills, error handler delegation, state transitions)
  - _process_final_order_state (FILLED with trade recovery, CANCELED,
    FAILED, trade update fallback on error)
  - Timing safeguard helpers (_record_order_status_update,
    _can_update_order_status, force_update bypass, boundary tests)
  - Lock management helpers (_get_order_status_lock, _cleanup_order_status_lock)
"""

import asyncio
import time
from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.xrpl import xrpl_constants as CONSTANTS
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee


class TestXRPLExchangeOrderStatus(XRPLExchangeTestBase, IsolatedAsyncioTestCase):
    """Tests for _request_order_status, _update_orders_with_error_handler,
    _process_final_order_state, and related helpers."""

    # -----------------------------------------------------------------
    # Helper: create a tracked InFlightOrder
    # -----------------------------------------------------------------
    def _make_order(
        self,
        client_order_id: str = "test_order",
        exchange_order_id: str = "12345-67890-ABCDEF",
        order_type: OrderType = OrderType.LIMIT,
        trade_type: TradeType = TradeType.BUY,
        amount: Decimal = Decimal("100"),
        price: Decimal = Decimal("1.0"),
        initial_state: OrderState = OrderState.OPEN,
        creation_timestamp: float = 1640000000.0,
    ) -> InFlightOrder:
        return InFlightOrder(
            client_order_id=client_order_id,
            exchange_order_id=exchange_order_id,
            trading_pair=self.trading_pair,
            order_type=order_type,
            trade_type=trade_type,
            amount=amount,
            price=price,
            initial_state=initial_state,
            creation_timestamp=creation_timestamp,
        )

    # =================================================================
    # _request_order_status – limit order status determination
    # =================================================================

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_limit_filled(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """Limit order with offer_changes status='filled' → FILLED"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()
        tx = {"tx": {"Sequence": 12345, "hash": "hash1", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            obc_mock.return_value = [
                {"maker_account": "rAccount", "offer_changes": [{"sequence": "12345", "status": "filled"}]}
            ]
            bc_mock.return_value = []

            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.FILLED, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_limit_partially_filled(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """Limit order with offer_changes status='partially-filled' → PARTIALLY_FILLED"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()
        tx = {"tx": {"Sequence": 12345, "hash": "h2", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            obc_mock.return_value = [
                {"maker_account": "rAccount", "offer_changes": [{"sequence": "12345", "status": "partially-filled"}]}
            ]
            bc_mock.return_value = []

            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.PARTIALLY_FILLED, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_limit_cancelled(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """Limit order with offer_changes status='cancelled' → CANCELED"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()
        tx = {"tx": {"Sequence": 12345, "hash": "h3", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            obc_mock.return_value = [
                {"maker_account": "rAccount", "offer_changes": [{"sequence": "12345", "status": "cancelled"}]}
            ]
            bc_mock.return_value = []

            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.CANCELED, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_limit_created_no_fill(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """Limit order with offer_changes status='created' and NO token balance changes → OPEN"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()
        tx = {"tx": {"Sequence": 12345, "hash": "h4", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            obc_mock.return_value = [
                {"maker_account": "rAccount", "offer_changes": [{"sequence": "12345", "status": "created"}]}
            ]
            # No balance changes or only XRP changes (fee deductions)
            bc_mock.return_value = []

            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.OPEN, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_limit_created_with_token_fill(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """Limit order with status='created' but token balance changes → PARTIALLY_FILLED
        (order partially crossed the book, remainder placed on book)"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()
        tx = {"tx": {"Sequence": 12345, "hash": "h_pf", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            obc_mock.return_value = [
                {"maker_account": "rAccount", "offer_changes": [{"sequence": "12345", "status": "created"}]}
            ]
            # Token balance changes indicate a partial fill occurred
            bc_mock.return_value = [
                {"account": "rAccount", "balances": [{"currency": "SOLO", "value": "10"}]}
            ]

            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.PARTIALLY_FILLED, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_no_offer_with_balance_change(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """No offer created but balance changes exist → FILLED (consumed immediately)"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()
        tx = {"tx": {"Sequence": 12345, "hash": "h5", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            obc_mock.return_value = []  # No offer changes
            bc_mock.return_value = [
                {"account": "rAccount", "balances": [{"some_balance": "data"}]}
            ]

            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.FILLED, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_no_offer_no_balance_change(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """No offer created AND no balance changes → FAILED"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()
        tx = {"tx": {"Sequence": 12345, "hash": "h6", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            obc_mock.return_value = []
            bc_mock.return_value = []

            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.FAILED, update.new_state)

    # =================================================================
    # _request_order_status – market order paths
    # =================================================================

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_market_order_success(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """Market order with tesSUCCESS → FILLED"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order(order_type=OrderType.MARKET)
        tx = {"tx": {"Sequence": 12345, "hash": "h_mkt", "ledger_index": 67890}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx]

        update = await self.connector._request_order_status(order)
        self.assertEqual(OrderState.FILLED, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_market_order_failed(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """Market order with tecFAILED → FAILED"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order(order_type=OrderType.MARKET)
        tx = {"tx": {"Sequence": 12345, "hash": "h_mkt_fail", "ledger_index": 67890}, "meta": {"TransactionResult": "tecFAILED"}}
        fetch_tx_mock.return_value = [tx]

        update = await self.connector._request_order_status(order)
        self.assertEqual(OrderState.FAILED, update.new_state)

    # =================================================================
    # _request_order_status – creation_tx_resp shortcut (market orders)
    # =================================================================

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    async def test_request_order_status_with_creation_tx_resp(
        self, network_mock, get_account_mock
    ):
        """When creation_tx_resp is provided, _fetch_account_transactions should NOT be called"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order(order_type=OrderType.MARKET)
        creation_resp = {
            "result": {
                "Sequence": 12345,
                "hash": "h_direct",
                "ledger_index": 67890,
                "meta": {"TransactionResult": "tesSUCCESS"},
            }
        }

        with patch.object(self.connector, "_fetch_account_transactions") as fetch_mock:
            update = await self.connector._request_order_status(order, creation_tx_resp=creation_resp)
            fetch_mock.assert_not_called()
            self.assertEqual(OrderState.FILLED, update.new_state)

    # =================================================================
    # _request_order_status – creation tx not found
    # =================================================================

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_not_found_pending_create_within_timeout(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """PENDING_CREATE order not found, within timeout → remains PENDING_CREATE"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order(initial_state=OrderState.PENDING_CREATE)
        # Set last_update_timestamp so it's within timeout
        order.last_update_timestamp = time.time() - 5  # 5 seconds ago, well within 120s timeout

        fetch_tx_mock.return_value = []  # No transactions found

        with patch("time.time", return_value=order.last_update_timestamp + 10):
            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.PENDING_CREATE, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_not_found_pending_create_timed_out(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """PENDING_CREATE order not found, past timeout → FAILED"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order(initial_state=OrderState.PENDING_CREATE)
        order.last_update_timestamp = 1000.0

        fetch_tx_mock.return_value = []

        with patch("time.time", return_value=1000.0 + CONSTANTS.PENDING_ORDER_STATUS_CHECK_TIMEOUT + 10):
            update = await self.connector._request_order_status(order)
            self.assertEqual(OrderState.FAILED, update.new_state)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_not_found_open_state_stays(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """OPEN order not found in tx history → remains OPEN (not pending so no timeout)"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order(initial_state=OrderState.OPEN)
        fetch_tx_mock.return_value = []

        update = await self.connector._request_order_status(order)
        self.assertEqual(OrderState.OPEN, update.new_state)

    # =================================================================
    # _request_order_status – exchange order id timeout
    # =================================================================

    async def test_request_order_status_exchange_id_timeout(self):
        """When get_exchange_order_id times out → returns current state"""
        order = self._make_order(exchange_order_id=None)
        # Make get_exchange_order_id timeout
        order.get_exchange_order_id = AsyncMock(side_effect=asyncio.TimeoutError)

        update = await self.connector._request_order_status(order)
        self.assertEqual(order.current_state, update.new_state)

    # =================================================================
    # _request_order_status – latest ledger index tracking
    # =================================================================

    @patch("hummingbot.connector.exchange.xrpl.xrpl_auth.XRPLAuth.get_account")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._ensure_network_started")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._fetch_account_transactions")
    async def test_request_order_status_uses_latest_ledger_index(
        self, fetch_tx_mock, network_mock, get_account_mock
    ):
        """When multiple txs match the sequence, use the one with the highest ledger_index"""
        get_account_mock.return_value = "rAccount"
        network_mock.return_value = None

        order = self._make_order()

        # Two txs: first shows 'created' at ledger 100, second shows 'filled' at ledger 200
        tx1 = {"tx": {"Sequence": 12345, "hash": "h1", "ledger_index": 100}, "meta": {"TransactionResult": "tesSUCCESS"}}
        tx2 = {"tx": {"Sequence": 99999, "hash": "h2", "ledger_index": 200}, "meta": {"TransactionResult": "tesSUCCESS"}}
        fetch_tx_mock.return_value = [tx1, tx2]

        with patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_order_book_changes") as obc_mock, \
             patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.get_balance_changes") as bc_mock:
            # First call (tx1 meta): our order created at ledger 100
            # Second call (tx2 meta): our order filled at ledger 200
            obc_mock.side_effect = [
                [{"maker_account": "rAccount", "offer_changes": [{"sequence": "12345", "status": "created"}]}],
                [{"maker_account": "rAccount", "offer_changes": [{"sequence": "12345", "status": "filled"}]}],
            ]
            bc_mock.return_value = []

            update = await self.connector._request_order_status(order)
            # Should use the latest (ledger 200) status = filled
            self.assertEqual(OrderState.FILLED, update.new_state)

    # =================================================================
    # _update_orders_with_error_handler
    # =================================================================

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._all_trade_updates_for_order")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    async def test_update_orders_skips_final_state_filled(self, status_mock, trade_mock):
        """Orders already in FILLED state should be skipped"""
        order = self._make_order(initial_state=OrderState.OPEN)
        # Transition to FILLED
        order.update_with_order_update(OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.FILLED,
        ))
        self.connector._order_tracker.start_tracking_order(order)

        error_handler = AsyncMock()
        await self.connector._update_orders_with_error_handler([order], error_handler)

        status_mock.assert_not_called()
        error_handler.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._all_trade_updates_for_order")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    async def test_update_orders_skips_final_state_canceled(self, status_mock, trade_mock):
        """Orders already in CANCELED state should be skipped"""
        order = self._make_order(initial_state=OrderState.OPEN)
        order.update_with_order_update(OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.CANCELED,
        ))
        self.connector._order_tracker.start_tracking_order(order)

        error_handler = AsyncMock()
        await self.connector._update_orders_with_error_handler([order], error_handler)

        status_mock.assert_not_called()
        error_handler.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._all_trade_updates_for_order")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    async def test_update_orders_skips_final_state_failed(self, status_mock, trade_mock):
        """Orders already in FAILED state should be skipped"""
        order = self._make_order(initial_state=OrderState.OPEN)
        order.update_with_order_update(OrderUpdate(
            client_order_id=order.client_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.FAILED,
        ))
        self.connector._order_tracker.start_tracking_order(order)

        error_handler = AsyncMock()
        await self.connector._update_orders_with_error_handler([order], error_handler)

        status_mock.assert_not_called()
        error_handler.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._all_trade_updates_for_order")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    async def test_update_orders_processes_open_order(self, status_mock, trade_mock):
        """OPEN order transitions to PARTIALLY_FILLED → status and trades are processed"""
        order = self._make_order()
        self.connector._order_tracker.start_tracking_order(order)

        update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.PARTIALLY_FILLED,
        )
        status_mock.return_value = update
        trade_mock.return_value = []

        error_handler = AsyncMock()
        await self.connector._update_orders_with_error_handler([order], error_handler)

        status_mock.assert_called_once_with(tracked_order=order)
        error_handler.assert_not_called()

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._all_trade_updates_for_order")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    async def test_update_orders_processes_filled_with_trades(self, status_mock, trade_mock):
        """OPEN → FILLED transition triggers trade update processing"""
        order = self._make_order()
        self.connector._order_tracker.start_tracking_order(order)

        update = OrderUpdate(
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.FILLED,
        )
        status_mock.return_value = update

        trade_update = TradeUpdate(
            trade_id="trade_123",
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_timestamp=time.time(),
            fill_price=Decimal("1.0"),
            fill_base_amount=Decimal("100"),
            fill_quote_amount=Decimal("100"),
            fee=AddedToCostTradeFee(flat_fees=[]),
        )
        trade_mock.return_value = [trade_update]

        error_handler = AsyncMock()
        await self.connector._update_orders_with_error_handler([order], error_handler)

        trade_mock.assert_called_once_with(order)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    async def test_update_orders_calls_error_handler_on_exception(self, status_mock):
        """Exception during status check calls the error handler"""
        order = self._make_order()
        self.connector._order_tracker.start_tracking_order(order)

        exc = Exception("Status check failed")
        status_mock.side_effect = exc

        error_handler = AsyncMock()
        await self.connector._update_orders_with_error_handler([order], error_handler)

        error_handler.assert_called_once_with(order, exc)

    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._all_trade_updates_for_order")
    @patch("hummingbot.connector.exchange.xrpl.xrpl_exchange.XrplExchange._request_order_status")
    async def test_update_orders_mixed_final_and_active(self, status_mock, trade_mock):
        """Only active orders should be status-checked; final-state orders skipped"""
        active_order = self._make_order(client_order_id="active_1")
        self.connector._order_tracker.start_tracking_order(active_order)

        filled_order = self._make_order(client_order_id="filled_1", exchange_order_id="99999-88888-CCCC")
        filled_order.update_with_order_update(OrderUpdate(
            client_order_id=filled_order.client_order_id,
            trading_pair=filled_order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.FILLED,
        ))
        self.connector._order_tracker.start_tracking_order(filled_order)

        update = OrderUpdate(
            client_order_id=active_order.client_order_id,
            exchange_order_id=active_order.exchange_order_id,
            trading_pair=active_order.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.OPEN,  # Same state → no update processed
        )
        status_mock.return_value = update
        trade_mock.return_value = []

        error_handler = AsyncMock()
        await self.connector._update_orders_with_error_handler([active_order, filled_order], error_handler)

        # Only active order's status should have been requested
        status_mock.assert_called_once_with(tracked_order=active_order)

    # =================================================================
    # _process_final_order_state
    # =================================================================

    async def test_process_final_order_state_filled_with_trade_update(self):
        """FILLED state processes all trade updates and cleans up lock"""
        order = self._make_order(client_order_id="fill_order_1", exchange_order_id="12345-1-AA")
        self.connector._order_tracker.start_tracking_order(order)

        trade_update = TradeUpdate(
            trade_id="trade_fill_1",
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_timestamp=time.time(),
            fill_price=Decimal("0.01"),
            fill_base_amount=Decimal("100"),
            fill_quote_amount=Decimal("1"),
            fee=AddedToCostTradeFee(flat_fees=[]),
        )

        self.connector._cleanup_order_status_lock = AsyncMock()
        self.connector._all_trade_updates_for_order = AsyncMock(return_value=[trade_update])

        await self.connector._process_final_order_state(
            order, OrderState.FILLED, time.time(), trade_update
        )

        self.connector._cleanup_order_status_lock.assert_called_once_with(order.client_order_id)
        self.connector._all_trade_updates_for_order.assert_called_once_with(order)

    async def test_process_final_order_state_canceled_without_trade(self):
        """CANCELED state without trade update still cleans up lock"""
        order = self._make_order(client_order_id="cancel_order_1", exchange_order_id="12345-2-BB")
        self.connector._order_tracker.start_tracking_order(order)

        self.connector._cleanup_order_status_lock = AsyncMock()

        await self.connector._process_final_order_state(
            order, OrderState.CANCELED, time.time()
        )

        self.connector._cleanup_order_status_lock.assert_called_once_with(order.client_order_id)

    async def test_process_final_order_state_failed(self):
        """FAILED state cleans up lock"""
        order = self._make_order(client_order_id="fail_order_1", exchange_order_id="12345-3-CC")
        self.connector._order_tracker.start_tracking_order(order)

        self.connector._cleanup_order_status_lock = AsyncMock()

        await self.connector._process_final_order_state(
            order, OrderState.FAILED, time.time()
        )

        self.connector._cleanup_order_status_lock.assert_called_once_with(order.client_order_id)

    async def test_process_final_order_state_filled_trade_recovery_error(self):
        """When _all_trade_updates_for_order raises, fallback to provided trade_update"""
        order = self._make_order(client_order_id="recovery_fail_1", exchange_order_id="12345-4-DD")
        self.connector._order_tracker.start_tracking_order(order)

        trade_update = TradeUpdate(
            trade_id="trade_fb_1",
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_timestamp=time.time(),
            fill_price=Decimal("0.01"),
            fill_base_amount=Decimal("100"),
            fill_quote_amount=Decimal("1"),
            fee=AddedToCostTradeFee(flat_fees=[]),
        )

        self.connector._cleanup_order_status_lock = AsyncMock()
        self.connector._all_trade_updates_for_order = AsyncMock(side_effect=Exception("Ledger error"))

        await self.connector._process_final_order_state(
            order, OrderState.FILLED, time.time(), trade_update
        )

        self.connector._cleanup_order_status_lock.assert_called_once()

    async def test_process_final_order_state_non_filled_with_trade_update(self):
        """CANCELED state with trade_update → trade_update is processed"""
        order = self._make_order(client_order_id="partial_cancel_1", exchange_order_id="12345-5-EE")
        self.connector._order_tracker.start_tracking_order(order)

        trade_update = TradeUpdate(
            trade_id="trade_pc_1",
            client_order_id=order.client_order_id,
            exchange_order_id=order.exchange_order_id,
            trading_pair=order.trading_pair,
            fill_timestamp=time.time(),
            fill_price=Decimal("0.01"),
            fill_base_amount=Decimal("50"),
            fill_quote_amount=Decimal("0.5"),
            fee=AddedToCostTradeFee(flat_fees=[]),
        )

        self.connector._cleanup_order_status_lock = AsyncMock()

        await self.connector._process_final_order_state(
            order, OrderState.CANCELED, time.time(), trade_update
        )

        self.connector._cleanup_order_status_lock.assert_called_once()

    # =================================================================
    # Lock management helpers
    # =================================================================

    def test_order_status_locks_initialized(self):
        """_order_status_locks dict is initialized"""
        self.assertIsInstance(self.connector._order_status_locks, dict)

    async def test_get_order_status_lock_creates_new(self):
        """_get_order_status_lock creates a new asyncio.Lock"""
        client_order_id = "lock_test"
        self.assertNotIn(client_order_id, self.connector._order_status_locks)

        lock = await self.connector._get_order_status_lock(client_order_id)

        self.assertIn(client_order_id, self.connector._order_status_locks)
        self.assertIsInstance(lock, asyncio.Lock)

    async def test_get_order_status_lock_returns_same_instance(self):
        """Calling _get_order_status_lock twice returns the same lock"""
        client_order_id = "same_lock_test"
        lock1 = await self.connector._get_order_status_lock(client_order_id)
        lock2 = await self.connector._get_order_status_lock(client_order_id)
        self.assertIs(lock1, lock2)

    async def test_get_order_status_lock_different_ids_different_locks(self):
        """Different order IDs get different locks"""
        lock1 = await self.connector._get_order_status_lock("order_a")
        lock2 = await self.connector._get_order_status_lock("order_b")
        self.assertIsNot(lock1, lock2)

    async def test_cleanup_order_status_lock(self):
        """_cleanup_order_status_lock removes lock"""
        client_order_id = "cleanup_test"
        await self.connector._get_order_status_lock(client_order_id)

        self.assertIn(client_order_id, self.connector._order_status_locks)

        await self.connector._cleanup_order_status_lock(client_order_id)

        self.assertNotIn(client_order_id, self.connector._order_status_locks)

    async def test_cleanup_order_status_lock_nonexistent(self):
        """Cleanup of non-existent order should not raise"""
        await self.connector._cleanup_order_status_lock("nonexistent")
        self.assertNotIn("nonexistent", self.connector._order_status_locks)

    async def test_cleanup_with_multiple_orders(self):
        """Cleanup of one order should not affect others"""
        ids = ["c1", "c2", "c3"]
        for oid in ids:
            await self.connector._get_order_status_lock(oid)

        await self.connector._cleanup_order_status_lock(ids[0])

        self.assertNotIn(ids[0], self.connector._order_status_locks)
        for oid in ids[1:]:
            self.assertIn(oid, self.connector._order_status_locks)

    # =================================================================
    # Misc helpers coverage
    # =================================================================

    def test_supported_order_types(self):
        """supported_order_types returns list containing LIMIT"""
        supported = self.connector.supported_order_types()
        self.assertIsInstance(supported, list)
        self.assertIn(OrderType.LIMIT, supported)

    def test_estimate_fee_pct(self):
        """estimate_fee_pct returns Decimal for maker and taker"""
        maker_fee = self.connector.estimate_fee_pct(is_maker=True)
        taker_fee = self.connector.estimate_fee_pct(is_maker=False)
        self.assertIsInstance(maker_fee, Decimal)
        self.assertIsInstance(taker_fee, Decimal)
