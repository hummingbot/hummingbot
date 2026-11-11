"""An order the tracker lost must still be cancellable on Gate spot.

``cancel`` takes a client order id and reads ``in_flight_orders``, so it only
reaches orders the running process placed. Gate spot agents rest maker orders
continuously, so a crash or archive with one live leaves an order that nothing can
clear — the same gap as the perpetual connector in #8552.

Gate's spot ``DELETE`` differs from the perpetual one: it requires
``currency_pair``, which is why this method demands the pair instead of guessing.
"""

import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.gate_io import gate_io_constants as CONSTANTS
from hummingbot.connector.exchange.gate_io.gate_io_exchange import GateIoExchange
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState

VENUE_ID = "347058646899348430"
PAIR = "COINALPHA-USDT"
EX_SYMBOL = "COINALPHA_USDT"


class GateIoCancelByExchangeOrderIdTest(unittest.TestCase):
    def setUp(self) -> None:
        # Never started: no network is touched. ``exchange_symbol_associated_to_pair``
        # needs trading rules, which an unstarted connector has not loaded.
        self.exchange = GateIoExchange(
            gate_io_api_key="testKey",
            gate_io_secret_key="testSecret",
            trading_pairs=[PAIR],
        )
        self._symbol_patch = patch.object(
            self.exchange,
            "exchange_symbol_associated_to_pair",
            new=AsyncMock(return_value=EX_SYMBOL),
        )
        self._symbol_patch.start()
        self.addCleanup(self._symbol_patch.stop)

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_an_untracked_order_is_cancelled_at_the_venue(self):
        """The case the tracker cannot reach: no in-flight order, venue id only."""
        self.assertEqual({}, dict(self.exchange.in_flight_orders))

        with patch.object(self.exchange, "_api_delete", new_callable=AsyncMock) as api_delete:
            result = self._run(
                self.exchange.cancel_by_exchange_order_id(PAIR, VENUE_ID)
            )

        self.assertEqual(VENUE_ID, result)
        api_delete.assert_awaited_once_with(
            path_url=CONSTANTS.ORDER_DELETE_PATH_URL.format(order_id=VENUE_ID),
            params={"currency_pair": EX_SYMBOL},
            is_auth_required=True,
            limit_id=CONSTANTS.ORDER_DELETE_LIMIT_ID,
        )

    def test_the_venue_symbol_is_used_not_the_pair_name(self):
        """Gate wants ``COINALPHA_USDT``, not ``COINALPHA-USDT``."""
        with patch.object(self.exchange, "_api_delete", new_callable=AsyncMock) as api_delete:
            self._run(self.exchange.cancel_by_exchange_order_id(PAIR, VENUE_ID))

        self.assertIsNotNone(api_delete.await_args)
        self.assertEqual({"currency_pair": EX_SYMBOL}, api_delete.await_args.kwargs["params"])

    def test_a_missing_pair_is_refused_before_any_call(self):
        """The spot DELETE cannot be addressed without it, so do not pretend."""
        with patch.object(self.exchange, "_api_delete", new_callable=AsyncMock) as api_delete:
            with self.assertRaises(ValueError) as ctx:
                self._run(self.exchange.cancel_by_exchange_order_id("", VENUE_ID))
        self.assertIn("trading pair", str(ctx.exception))
        api_delete.assert_not_awaited()

    def test_a_tracked_order_is_marked_cancelled(self):
        order = InFlightOrder(
            client_order_id="HBOT-1",
            trading_pair=PAIR,
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id=VENUE_ID,
        )
        # ``in_flight_orders`` is the dict the tracker reads; ``_in_flight_orders``
        # is a container nothing consults.
        self.exchange.in_flight_orders[order.client_order_id] = order

        with patch.object(self.exchange, "_api_delete", new_callable=AsyncMock):
            self._run(self.exchange.cancel_by_exchange_order_id(PAIR, VENUE_ID))

        self.assertEqual(OrderState.CANCELED, order.current_state)

    def test_a_venue_rejection_surfaces_to_the_caller(self):
        with patch.object(
            self.exchange,
            "_api_delete",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ORDER_NOT_FOUND"),
        ):
            with self.assertRaises(RuntimeError):
                self._run(self.exchange.cancel_by_exchange_order_id(PAIR, VENUE_ID))
