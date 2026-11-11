"""An order the tracker lost must still be cancellable on Gate perpetual.

``cancel`` takes a client order id and reads ``in_flight_orders``, so it only
reaches orders the running process placed. When a session crashes, is archived or
is restarted while an order rests, the order is still live at the venue and the
API has no way to reach it — hummingbot-api's
``POST /trading/{acct}/{conn}/orders/by-exchange-id/{id}/cancel`` answered 501 for
this connector, and a live Gate agent reported "14 stale prior-session OPEN
orders remain with no cancel tool available to me".

Gate's REST takes the venue order id directly, so the connector can do this
without the tracker. It must also settle the tracked order's state when it *does*
recognise the id, or the control loop cancels it again on the next tick.
"""
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.gate_io_perpetual import (
    gate_io_perpetual_constants as CONSTANTS,
)
from hummingbot.connector.derivative.gate_io_perpetual.gate_io_perpetual_derivative import (
    GateIoPerpetualDerivative,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class GateIoPerpetualCancelByExchangeOrderIdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = GateIoPerpetualDerivative(
            gate_io_perpetual_api_key="testKey",
            gate_io_perpetual_secret_key="testSecret",
            gate_io_perpetual_user_id="testUser",
            trading_pairs=["BTC-USDT"],
        )

    def _traded_pair(self) -> str:
        return "BTC-USDT"

    def test_an_untracked_order_is_cancelled_at_the_venue(self):
        """The case the tracker cannot reach: no in-flight order, venue id only."""
        self.assertEqual({}, self.exchange.in_flight_orders)

        with patch.object(
            self.exchange, "_api_delete", new_callable=AsyncMock
        ) as api_delete:
            result = asyncio.get_event_loop().run_until_complete(
                self.exchange.cancel_by_exchange_order_id(
                    self._traded_pair(), "347058646899348430"
                )
            )

        self.assertEqual("347058646899348430", result)
        api_delete.assert_awaited_once_with(
            path_url=CONSTANTS.ORDER_DELETE_PATH_URL.format(id="347058646899348430"),
            is_auth_required=True,
            limit_id=CONSTANTS.CANCEL_ORDERS_LIMITS_ID,
        )

    def test_the_url_carries_the_venue_id_not_a_client_order_id(self):
        path = CONSTANTS.ORDER_DELETE_PATH_URL.format(id="99887766")
        self.assertIn("99887766", path)
        self.assertNotIn("{id}", path)

    def test_a_tracked_order_is_marked_cancelled(self):
        """Otherwise the next control-loop tick cancels it again and logs a failure."""
        order = InFlightOrder(
            client_order_id="HBOT-1",
            trading_pair=self._traded_pair(),
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id="347058646899348430",
        )
        # ``in_flight_orders`` is the dict the tracker itself reads; assigning to
        # ``_in_flight_orders`` populates a container nothing consults.
        self.exchange.in_flight_orders[order.client_order_id] = order

        with patch.object(
            self.exchange, "_api_delete", new_callable=AsyncMock
        ):
            asyncio.get_event_loop().run_until_complete(
                self.exchange.cancel_by_exchange_order_id(
                    self._traded_pair(), "347058646899348430"
                )
            )

        self.assertEqual(OrderState.CANCELED, order.current_state)

    def test_a_venue_rejection_surfaces_to_the_caller(self):
        """An API error must not be reported as a cancellation."""
        with patch.object(
            self.exchange,
            "_api_delete",
            new_callable=AsyncMock,
            side_effect=RuntimeError("ORDER_NOT_FOUND"),
        ):
            with self.assertRaises(RuntimeError):
                asyncio.get_event_loop().run_until_complete(
                    self.exchange.cancel_by_exchange_order_id(
                        self._traded_pair(), "0"
                    )
                )
