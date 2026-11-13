"""An order the tracker lost must still be cancellable on Binance USD-M perpetual.

``cancel`` resolves a client order id through ``in_flight_orders``, so an order that
outlived its executor -- crash, archive, restart -- cannot be reached: it rests,
holds margin and can still fill. Binance USD-M takes its own ``orderId`` on the same
DELETE the connector already uses, so the venue can be addressed directly.
"""
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.binance_perpetual import (
    binance_perpetual_constants as CONSTANTS,
)
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import (
    BinancePerpetualDerivative,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class BinancePerpetualCancelByExchangeOrderIdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = BinancePerpetualDerivative(
            binance_perpetual_api_key="testKey",
            binance_perpetual_api_secret="testSecret",
            trading_pairs=["BTC-USDT", "ETH-USDT"],
        )

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_cancels_with_symbol_and_venue_order_id(self):
        deleted = {}

        async def fake_delete(path_url, params=None, is_auth_required=False, limit_id=None, **kwargs):
            deleted["path_url"] = path_url
            deleted["params"] = params
            deleted["limit_id"] = limit_id
            deleted["kwargs"] = kwargs
            return {"status": "CANCELED", "orderId": 999}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTCUSDT")),
            patch.object(self.exchange, "_api_delete", side_effect=fake_delete),
        ):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "999"))

        self.assertEqual("999", result)
        self.assertEqual(CONSTANTS.ORDER_URL, deleted["path_url"])
        self.assertEqual("BTCUSDT", deleted["params"]["symbol"])
        self.assertEqual("999", deleted["params"]["orderId"])
        self.assertEqual(CONSTANTS.DELETE_ORDER_LIMIT_ID, deleted["limit_id"])
        self.assertTrue(deleted["kwargs"].get("return_err"), "return_err=True is required")

    def test_unknown_order_counts_as_cancelled(self):
        async def fake_delete(path_url, params=None, is_auth_required=False, limit_id=None, **kwargs):
            return {"code": -2011, "msg": "Unknown order sent."}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTCUSDT")),
            patch.object(self.exchange, "_api_delete", side_effect=fake_delete),
        ):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "404"))

        self.assertEqual("404", result)

    def test_venue_rejection_raises_with_the_cause(self):
        async def fake_delete(path_url, params=None, is_auth_required=False, limit_id=None, **kwargs):
            return {"code": -1121, "msg": "Invalid symbol."}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTCUSDT")),
            patch.object(self.exchange, "_api_delete", side_effect=fake_delete),
        ):
            with self.assertRaises(IOError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "1"))

    def test_empty_order_id_is_refused_before_any_request(self):
        deleted = AsyncMock()

        with patch.object(self.exchange, "_api_delete", deleted):
            with self.assertRaises(ValueError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", ""))

        deleted.assert_not_called()

    def test_order_on_another_pair_is_not_settled(self):
        """Binance allocates order ids per symbol, so the id alone identifies nothing."""
        async def fake_delete(path_url, params=None, is_auth_required=False, limit_id=None, **kwargs):
            return {"status": "CANCELED"}

        order = InFlightOrder(
            client_order_id="HBOT-2",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id="999",
        )
        self.exchange.in_flight_orders[order.client_order_id] = order

        processed = []
        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTCUSDT")),
            patch.object(self.exchange, "_api_delete", side_effect=fake_delete),
            patch.object(
                self.exchange._order_tracker,
                "process_order_update",
                side_effect=lambda update: processed.append(update) or True,
            ),
        ):
            self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "999"))

        self.assertEqual([], processed, "cancelling on BTC-USDT settled an ETH-USDT order")
        self.assertIn("HBOT-2", self.exchange.in_flight_orders)

    def test_tracked_order_is_settled_through_the_tracker(self):
        """The OrderCancelled event must fire, not just the state field change.

        The spy calls through to the real tracker method, so this fails if the
        connector stops publishing the update rather than merely if the call shape
        changes.
        """
        async def fake_delete(path_url, params=None, is_auth_required=False, limit_id=None, **kwargs):
            return {"status": "CANCELED"}

        order = InFlightOrder(
            client_order_id="HBOT-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id="999",
        )
        self.exchange.in_flight_orders[order.client_order_id] = order

        processed = []
        real_process = self.exchange._order_tracker.process_order_update

        def spy(update):
            processed.append(update)
            return real_process(update)

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTCUSDT")),
            patch.object(self.exchange, "_api_delete", side_effect=fake_delete),
            patch.object(self.exchange._order_tracker, "process_order_update", side_effect=spy),
        ):
            self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "999"))

        self.assertEqual(1, len(processed), "the tracker never saw the cancellation")
        update = processed[0]
        self.assertEqual(OrderState.CANCELED, update.new_state)
        self.assertEqual("HBOT-1", update.client_order_id)
        # The tracker consumes the update synchronously and must have moved the
        # order to CANCELED -- re-applying it returns False, which is exactly why
        # the event has to come from the tracker and not from a field assignment.
        self.assertEqual(OrderState.CANCELED, order.current_state)


if __name__ == "__main__":
    unittest.main()
