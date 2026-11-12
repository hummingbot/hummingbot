"""An order the tracker lost must still be cancellable on Derive perpetual.

``cancel`` reads the order id off the tracked order, so an order whose owning process
is gone cannot be cancelled at all: it rests, holds margin and can still fill.
Derive's private/cancel takes the ``order_id`` directly.
"""
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import hummingbot.connector.derivative.derive_perpetual.derive_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.derive_perpetual.derive_perpetual_derivative import (
    DerivePerpetualDerivative,
)

CANCEL_PATH = CONSTANTS.CANCEL_ORDER_URL
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class DeriveCancelByExchangeOrderIdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = DerivePerpetualDerivative(
            derive_perpetual_wallet_address="0x" + "11" * 20,
            session_private_key="11" * 32,
            subacct_id=12345,
            trading_pairs=["BTC-USDT", "ETH-USDT"],
        )

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_cancels_with_instrument_and_order_id(self):
        posted = {}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            posted["path_url"] = path_url
            posted["data"] = data
            return {"result": {"order_status": "cancelled"}}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC-PERP")),
            patch.object(self.exchange, "_api_post", side_effect=fake_post),
        ):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "abc-123"))

        self.assertEqual("abc-123", result)
        self.assertEqual(CANCEL_PATH, posted["path_url"])
        self.assertEqual("BTC-PERP", posted["data"]["instrument_name"])
        self.assertEqual("abc-123", posted["data"]["order_id"])
        self.assertEqual(12345, posted["data"]["subaccount_id"])

    def test_empty_order_id_is_refused_before_any_request(self):
        posted = AsyncMock()

        with patch.object(self.exchange, "_api_post", posted):
            with self.assertRaises(ValueError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", ""))

        posted.assert_not_called()

    def test_venue_rejection_raises_with_the_cause(self):
        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"error": {"code": -32000, "message": "Order not found"}}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC-PERP")),
            patch.object(self.exchange, "_api_post", side_effect=fake_post),
        ):
            with self.assertRaises(IOError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "404"))

    def test_unconfirmed_cancel_raises(self):
        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"result": {"order_status": "open"}}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC-PERP")),
            patch.object(self.exchange, "_api_post", side_effect=fake_post),
        ):
            with self.assertRaises(IOError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "abc-123"))

    def test_tracked_order_is_settled_through_the_tracker(self):
        """The OrderCancelled event must fire, not just the state field change.

        The spy calls through to the real tracker method, so this fails if the
        connector stops publishing the update.
        """
        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"result": {"order_status": "cancelled"}}

        order = InFlightOrder(
            client_order_id="HBOT-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id="abc-123",
        )
        self.exchange.in_flight_orders[order.client_order_id] = order

        processed = []
        real_process = self.exchange._order_tracker.process_order_update

        def spy(update):
            processed.append(update)
            return real_process(update)

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC-PERP")),

            patch.object(self.exchange, "_api_post", side_effect=fake_post),
            patch.object(self.exchange._order_tracker, "process_order_update", side_effect=spy),
        ):
            self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "abc-123"))

        self.assertEqual(1, len(processed), "the tracker never saw the cancellation")
        self.assertEqual(OrderState.CANCELED, processed[0].new_state)
        self.assertEqual("HBOT-1", processed[0].client_order_id)
        self.assertEqual(OrderState.CANCELED, order.current_state)

    def test_order_on_another_pair_is_not_settled(self):
        """A venue id is not unique across pairs; only the named order may move."""

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"result": {"order_status": "cancelled"}}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"result": {"order_status": "cancelled"}}

        order = InFlightOrder(
            client_order_id="HBOT-2",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id="abc-123",
        )
        self.exchange.in_flight_orders[order.client_order_id] = order

        processed = []
        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC-PERP")),

            patch.object(self.exchange, "_api_post", side_effect=fake_post),
            patch.object(
                self.exchange._order_tracker,
                "process_order_update",
                side_effect=lambda update: processed.append(update) or True,
            ),
        ):
            self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "abc-123"))

        self.assertEqual([], processed, "cancelling on BTC-USDT settled an ETH-USDT order")
        self.assertIn("HBOT-2", self.exchange.in_flight_orders)


if __name__ == "__main__":
    unittest.main()
