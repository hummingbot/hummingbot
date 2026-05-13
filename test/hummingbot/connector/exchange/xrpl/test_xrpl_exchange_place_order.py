"""
Chunk 4 – Place Order tests for XrplExchange.

Covers:
    - ``_place_order``  (limit buy/sell, market, submission failure,
      verification failure, not accepted, unknown market)
    - ``_place_order_and_process_update``  (OPEN, FILLED, PARTIALLY_FILLED,
      trade-fill None, exception → FAILED)
    - ``buy`` / ``sell``  (client order-id prefix, LIMIT / MARKET)
"""

import time
import unittest
from decimal import Decimal
from test.hummingbot.connector.exchange.xrpl.test_xrpl_exchange_base import XRPLExchangeTestBase
from unittest.mock import AsyncMock, MagicMock, patch

from xrpl.models import Response
from xrpl.models.response import ResponseStatus

from hummingbot.connector.exchange.xrpl.xrpl_worker_pool import TransactionSubmitResult
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState, OrderUpdate

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

_STRATEGY_FACTORY_PATH = (
    "hummingbot.connector.exchange.xrpl.xrpl_exchange.OrderPlacementStrategyFactory"
)


def _make_inflight_order(
    client_order_id: str = "hbot-test-001",
    trading_pair: str = "SOLO-XRP",
    order_type: OrderType = OrderType.LIMIT,
    trade_type: TradeType = TradeType.BUY,
    amount: Decimal = Decimal("100"),
    price: Decimal = Decimal("0.5"),
) -> InFlightOrder:
    return InFlightOrder(
        client_order_id=client_order_id,
        trading_pair=trading_pair,
        order_type=order_type,
        trade_type=trade_type,
        amount=amount,
        price=price,
        creation_timestamp=time.time(),
    )


# --------------------------------------------------------------------------- #
# Test class
# --------------------------------------------------------------------------- #


class TestXRPLExchangePlaceOrder(XRPLExchangeTestBase, unittest.IsolatedAsyncioTestCase):
    """Tests for _place_order, _place_order_and_process_update, buy, and sell."""

    # ------------------------------------------------------------------ #
    # _place_order — success paths
    # ------------------------------------------------------------------ #

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_limit_buy_order_success(self, factory_mock):
        """Limit BUY → strategy + tx_pool + verification → returns (exchange_order_id, timestamp, response)."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=12345, prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890-ABCDEF", tx_hash="HASH1",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        exchange_order_id, transact_time, resp = await self.connector._place_order(
            order_id="hbot-buy-1",
            trading_pair=self.trading_pair,
            amount=Decimal("100"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("0.5"),
        )

        self.assertEqual(exchange_order_id, "12345-67890-ABCDEF")
        self.assertGreater(transact_time, 0)
        self.assertIsNotNone(resp)
        factory_mock.create_strategy.assert_called_once()
        mock_strategy.create_order_transaction.assert_awaited_once()

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_limit_sell_order_success(self, factory_mock):
        """Limit SELL order succeeds through the same path."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=22222, prelim_result="tesSUCCESS",
            exchange_order_id="22222-99999-XYZ", tx_hash="HASH2",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        exchange_order_id, _, resp = await self.connector._place_order(
            order_id="hbot-sell-1",
            trading_pair=self.trading_pair,
            amount=Decimal("50"),
            trade_type=TradeType.SELL,
            order_type=OrderType.LIMIT,
            price=Decimal("1.0"),
        )

        self.assertEqual(exchange_order_id, "22222-99999-XYZ")
        self.assertIsNotNone(resp)

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_market_order_success(self, factory_mock):
        """Market order uses the same worker-pool flow."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=33333, prelim_result="tesSUCCESS",
            exchange_order_id="33333-11111-MKT", tx_hash="HASH3",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        exchange_order_id, _, resp = await self.connector._place_order(
            order_id="hbot-mkt-1",
            trading_pair=self.trading_pair,
            amount=Decimal("10"),
            trade_type=TradeType.BUY,
            order_type=OrderType.MARKET,
            price=Decimal("0.5"),
        )

        self.assertEqual(exchange_order_id, "33333-11111-MKT")
        self.assertIsNotNone(resp)

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_limit_order_usd_pair(self, factory_mock):
        """Limit order on SOLO-USD pair succeeds."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=44444, prelim_result="tesSUCCESS",
            exchange_order_id="44444-55555-USD", tx_hash="HASH4",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        exchange_order_id, _, _ = await self.connector._place_order(
            order_id="hbot-usd-1",
            trading_pair=self.trading_pair_usd,
            amount=Decimal("100"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("2.5"),
        )

        self.assertEqual(exchange_order_id, "44444-55555-USD")

    # ------------------------------------------------------------------ #
    # _place_order — PENDING_CREATE state transition
    # ------------------------------------------------------------------ #

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_sets_pending_create(self, factory_mock):
        """_place_order pushes PENDING_CREATE to the order tracker."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(success=True, sequence=12345, prelim_result="tesSUCCESS")
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        with patch.object(
            self.connector._order_tracker, "process_order_update"
        ) as tracker_mock:
            await self.connector._place_order(
                order_id="hbot-pending-1",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("0.5"),
            )

            # PENDING_CREATE update should have been sent
            self.assertTrue(tracker_mock.called)
            update: OrderUpdate = tracker_mock.call_args[0][0]
            self.assertEqual(update.new_state, OrderState.PENDING_CREATE)
            self.assertEqual(update.client_order_id, "hbot-pending-1")

    # ------------------------------------------------------------------ #
    # _place_order — failure paths
    # ------------------------------------------------------------------ #

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_submission_failure(self, factory_mock):
        """Submission failure (success=False) raises exception."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(success=False, prelim_result="tecUNFUNDED_OFFER")

        with self.assertRaises(Exception) as ctx:
            await self.connector._place_order(
                order_id="hbot-fail-1",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("0.5"),
            )

        self.assertIn("creation failed", str(ctx.exception))

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_verification_failure(self, factory_mock):
        """Verification failure raises exception."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(success=True, sequence=12345, prelim_result="tesSUCCESS")
        self._mock_verification_pool(verified=False, final_result="tecKILLED")

        with self.assertRaises(Exception) as ctx:
            await self.connector._place_order(
                order_id="hbot-verify-fail",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("0.5"),
            )

        self.assertIn("creation failed", str(ctx.exception))

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_not_accepted(self, factory_mock):
        """Transaction not accepted (prelim_result not tesSUCCESS/terQUEUED) raises."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        # Create a submit result where is_accepted is False
        signed_tx = MagicMock()
        signed_tx.sequence = 12345
        signed_tx.last_ledger_sequence = 67890

        result = TransactionSubmitResult(
            success=True,
            signed_tx=signed_tx,
            response=Response(
                status=ResponseStatus.SUCCESS,
                result={"engine_result": "tecPATH_DRY"},
            ),
            prelim_result="tecPATH_DRY",
            exchange_order_id="12345-67890-XX",
            tx_hash="HASHX",
        )
        mock_pool = MagicMock()
        mock_pool.submit_transaction = AsyncMock(return_value=result)
        self.connector._tx_pool = mock_pool

        with self.assertRaises(Exception) as ctx:
            await self.connector._place_order(
                order_id="hbot-notacc-1",
                trading_pair=self.trading_pair,
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal("0.5"),
            )

        self.assertIn("creation failed", str(ctx.exception))

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_strategy_exception(self, factory_mock):
        """Exception from create_order_transaction propagates."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(
            side_effect=ValueError("Market NOT_FOUND not found in markets list")
        )
        factory_mock.create_strategy.return_value = mock_strategy

        with self.assertRaises(Exception) as ctx:
            await self.connector._place_order(
                order_id="hbot-exc-1",
                trading_pair="NOT_FOUND",
                amount=Decimal("1"),
                trade_type=TradeType.BUY,
                order_type=OrderType.MARKET,
                price=Decimal("1"),
            )

        self.assertIn("creation failed", str(ctx.exception))

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_queued_result_accepted(self, factory_mock):
        """terQUEUED is considered accepted and proceeds to verification."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        # terQUEUED should be treated as accepted
        signed_tx = MagicMock()
        signed_tx.sequence = 12345
        signed_tx.last_ledger_sequence = 67890

        result = TransactionSubmitResult(
            success=True,
            signed_tx=signed_tx,
            response=Response(
                status=ResponseStatus.SUCCESS,
                result={"engine_result": "terQUEUED"},
            ),
            prelim_result="terQUEUED",
            exchange_order_id="12345-67890-QUE",
            tx_hash="HASHQ",
        )
        mock_pool = MagicMock()
        mock_pool.submit_transaction = AsyncMock(return_value=result)
        self.connector._tx_pool = mock_pool

        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        exchange_order_id, _, resp = await self.connector._place_order(
            order_id="hbot-queued",
            trading_pair=self.trading_pair,
            amount=Decimal("10"),
            trade_type=TradeType.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("0.5"),
        )

        self.assertEqual(exchange_order_id, "12345-67890-QUE")
        self.assertIsNotNone(resp)

    # ------------------------------------------------------------------ #
    # _place_order_and_process_update
    # ------------------------------------------------------------------ #

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_and_process_update_open(self, factory_mock):
        """When _request_order_status returns OPEN, order tracker gets OPEN update."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=12345, prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890-ABCDEF",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        order = _make_inflight_order(client_order_id="hbot-open-1")

        open_update = OrderUpdate(
            client_order_id="hbot-open-1",
            exchange_order_id="12345-67890-ABCDEF",
            trading_pair=self.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.OPEN,
        )

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=open_update
        ), patch.object(
            self.connector._order_tracker, "process_order_update"
        ) as tracker_mock:
            result = await self.connector._place_order_and_process_update(order)

        self.assertEqual(result, "12345-67890-ABCDEF")
        # Should receive two updates: PENDING_CREATE from _place_order + OPEN from process_update
        # But since _place_order's tracker call also goes to the mock, we check for at least one OPEN
        found_open = any(
            call[0][0].new_state == OrderState.OPEN
            for call in tracker_mock.call_args_list
        )
        self.assertTrue(found_open, "Expected OPEN state update to be processed")

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_and_process_update_filled(self, factory_mock):
        """When _request_order_status returns FILLED, _process_final_order_state is called."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=12345, prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890-FILL",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        order = _make_inflight_order(
            client_order_id="hbot-filled-1",
            order_type=OrderType.MARKET,
        )

        filled_update = OrderUpdate(
            client_order_id="hbot-filled-1",
            exchange_order_id="12345-67890-FILL",
            trading_pair=self.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.FILLED,
        )

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=filled_update
        ), patch.object(
            self.connector, "_process_final_order_state", new_callable=AsyncMock
        ) as final_mock:
            result = await self.connector._place_order_and_process_update(order)

        self.assertEqual(result, "12345-67890-FILL")
        final_mock.assert_awaited_once()
        # Verify it was called with FILLED state
        call_args = final_mock.call_args
        self.assertEqual(call_args[0][1], OrderState.FILLED)

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_and_process_update_partially_filled(self, factory_mock):
        """PARTIALLY_FILLED → process_order_update + process_trade_fills."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=12345, prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890-PART",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        order = _make_inflight_order(client_order_id="hbot-partial-1")

        partial_update = OrderUpdate(
            client_order_id="hbot-partial-1",
            exchange_order_id="12345-67890-PART",
            trading_pair=self.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.PARTIALLY_FILLED,
        )

        mock_trade_update = MagicMock()

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=partial_update
        ), patch.object(
            self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=mock_trade_update
        ) as fills_mock, patch.object(
            self.connector._order_tracker, "process_order_update"
        ), patch.object(
            self.connector._order_tracker, "process_trade_update"
        ) as trade_tracker_mock:
            result = await self.connector._place_order_and_process_update(order)

        self.assertEqual(result, "12345-67890-PART")
        fills_mock.assert_awaited_once()
        trade_tracker_mock.assert_called_once_with(mock_trade_update)

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_and_process_update_partially_filled_no_trade(self, factory_mock):
        """PARTIALLY_FILLED with process_trade_fills returning None logs error."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(return_value=MagicMock())
        factory_mock.create_strategy.return_value = mock_strategy

        self._mock_tx_pool(
            success=True, sequence=12345, prelim_result="tesSUCCESS",
            exchange_order_id="12345-67890-NOTR",
        )
        self._mock_verification_pool(verified=True, final_result="tesSUCCESS")

        order = _make_inflight_order(client_order_id="hbot-partial-notrade")

        partial_update = OrderUpdate(
            client_order_id="hbot-partial-notrade",
            exchange_order_id="12345-67890-NOTR",
            trading_pair=self.trading_pair,
            update_timestamp=time.time(),
            new_state=OrderState.PARTIALLY_FILLED,
        )

        with patch.object(
            self.connector, "_request_order_status", new_callable=AsyncMock, return_value=partial_update
        ), patch.object(
            self.connector, "process_trade_fills", new_callable=AsyncMock, return_value=None
        ), patch.object(
            self.connector._order_tracker, "process_order_update"
        ), patch.object(
            self.connector._order_tracker, "process_trade_update"
        ) as trade_tracker_mock:
            result = await self.connector._place_order_and_process_update(order)

        self.assertEqual(result, "12345-67890-NOTR")
        # process_trade_update should NOT have been called since fills returned None
        trade_tracker_mock.assert_not_called()

    @patch(_STRATEGY_FACTORY_PATH)
    async def test_place_order_and_process_update_exception_sets_failed(self, factory_mock):
        """Exception in _place_order → FAILED state, re-raises."""
        mock_strategy = MagicMock()
        mock_strategy.create_order_transaction = AsyncMock(
            side_effect=RuntimeError("network error")
        )
        factory_mock.create_strategy.return_value = mock_strategy

        order = _make_inflight_order(client_order_id="hbot-fail-proc")

        with patch.object(
            self.connector._order_tracker, "process_order_update"
        ) as tracker_mock:
            with self.assertRaises(Exception):
                await self.connector._place_order_and_process_update(order)

        # The last update should be FAILED
        last_update: OrderUpdate = tracker_mock.call_args[0][0]
        self.assertEqual(last_update.new_state, OrderState.FAILED)
        self.assertEqual(last_update.client_order_id, "hbot-fail-proc")

    # ------------------------------------------------------------------ #
    # buy / sell
    # ------------------------------------------------------------------ #

    def test_buy_returns_client_order_id_with_prefix(self):
        """buy() returns an order_id starting with 'hbot'."""
        # buy() calls safe_ensure_future which requires a running loop but
        # returns the order id synchronously, so we just need to patch
        # _create_order to prevent actual execution.
        with patch.object(self.connector, "_create_order", new_callable=AsyncMock):
            order_id = self.connector.buy(
                self.trading_pair,
                Decimal("100"),
                OrderType.LIMIT,
                Decimal("0.5"),
            )

        self.assertTrue(order_id.startswith("hbot"))

    def test_sell_returns_client_order_id_with_prefix(self):
        """sell() returns an order_id starting with 'hbot'."""
        with patch.object(self.connector, "_create_order", new_callable=AsyncMock):
            order_id = self.connector.sell(
                self.trading_pair,
                Decimal("100"),
                OrderType.LIMIT,
                Decimal("0.5"),
            )

        self.assertTrue(order_id.startswith("hbot"))

    def test_buy_market_order_returns_prefix(self):
        """buy() with MARKET order type still returns hbot-prefixed id."""
        with patch.object(self.connector, "_create_order", new_callable=AsyncMock):
            order_id = self.connector.buy(
                self.trading_pair_usd,
                Decimal("50"),
                OrderType.MARKET,
                Decimal("1.0"),
            )

        self.assertTrue(order_id.startswith("hbot"))

    def test_sell_market_order_returns_prefix(self):
        """sell() with MARKET order type returns hbot-prefixed id."""
        with patch.object(self.connector, "_create_order", new_callable=AsyncMock):
            order_id = self.connector.sell(
                self.trading_pair_usd,
                Decimal("50"),
                OrderType.MARKET,
                Decimal("1.0"),
            )

        self.assertTrue(order_id.startswith("hbot"))

    def test_buy_and_sell_return_different_ids(self):
        """Each call to buy/sell generates a unique order id."""
        with patch.object(self.connector, "_create_order", new_callable=AsyncMock):
            id1 = self.connector.buy(self.trading_pair, Decimal("1"), OrderType.LIMIT, Decimal("0.5"))
            id2 = self.connector.buy(self.trading_pair, Decimal("1"), OrderType.LIMIT, Decimal("0.5"))
            id3 = self.connector.sell(self.trading_pair, Decimal("1"), OrderType.LIMIT, Decimal("0.5"))

        self.assertNotEqual(id1, id2)
        self.assertNotEqual(id1, id3)
        self.assertNotEqual(id2, id3)


if __name__ == "__main__":
    unittest.main()
