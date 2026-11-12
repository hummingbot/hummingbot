"""An order the tracker lost must still be cancellable on Hyperliquid perpetual.

``cancel`` sends the ``cloid``, which only exists for orders this process placed. An
order that outlives its session -- crash, archive, restart mid-winddown -- is still
live at the venue and holds margin, and hummingbot-api's
``POST /trading/{acct}/{conn}/orders/by-exchange-id/{id}/cancel`` answers 501 without
this method.

Hyperliquid identifies an order by its numeric ``oid`` inside the cancel action, and
that number survives the process.
"""
import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.hyperliquid_perpetual import (
    hyperliquid_perpetual_constants as CONSTANTS,
)
from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_derivative import (
    HyperliquidPerpetualDerivative,
)
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderState


class HyperliquidCancelByExchangeOrderIdTest(unittest.TestCase):
    def setUp(self) -> None:
        self.exchange = HyperliquidPerpetualDerivative(
            hyperliquid_perpetual_secret_key="11" * 32,
            # address derived from the (dummy) key above -- the connector validates the pair
            hyperliquid_perpetual_address="0x19E7E376E7C213B7E7e7e46cc70A5dD086DAff2A",
            trading_pairs=["BTC-USDT", "ETH-USDT"],
        )
        self.exchange.coin_to_asset["BTC"] = 3

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_cancels_by_oid_with_the_asset(self):
        posted = {}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            posted["path_url"] = path_url
            posted["data"] = data
            return {"status": "ok", "response": {"data": {"statuses": ["success"]}}}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC")),
            patch.object(self.exchange, "_api_post", side_effect=fake_post),
        ):
            result = self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "12345"))

        self.assertEqual("12345", result)
        self.assertEqual(CONSTANTS.CANCEL_ORDER_URL, posted["path_url"])
        self.assertEqual("cancel", posted["data"]["type"])
        self.assertEqual({"asset": 3, "oid": 12345}, posted["data"]["cancels"])

    def test_non_numeric_order_id_is_refused_before_any_request(self):
        posted = AsyncMock()

        with patch.object(self.exchange, "_api_post", posted):
            with self.assertRaises(ValueError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "not-an-oid"))

        posted.assert_not_called()

    def test_empty_order_id_is_refused_before_any_request(self):
        posted = AsyncMock()

        with patch.object(self.exchange, "_api_post", posted):
            with self.assertRaises(ValueError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", ""))

        posted.assert_not_called()

    def test_venue_rejection_raises_with_the_cause(self):
        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"status": "ok", "response": {"data": {"statuses": [{"error": "Order not found"}]}}}

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC")),
            patch.object(self.exchange, "_api_post", side_effect=fake_post),
        ):
            with self.assertRaises(IOError):
                self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "404"))

    def test_tracked_order_is_settled_through_the_tracker(self):
        """The OrderCancelled event must fire, not just the state field change.

        The spy calls through to the real tracker method, so this fails if the
        connector stops publishing the update.
        """
        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"status": "ok", "response": {"data": {"statuses": ["success"]}}}

        order = InFlightOrder(
            client_order_id="HBOT-1",
            trading_pair="BTC-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id="12345",
        )
        self.exchange.in_flight_orders[order.client_order_id] = order

        processed = []
        real_process = self.exchange._order_tracker.process_order_update

        def spy(update):
            processed.append(update)
            return real_process(update)

        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC")),

            patch.object(self.exchange, "_api_post", side_effect=fake_post),
            patch.object(self.exchange._order_tracker, "process_order_update", side_effect=spy),
        ):
            self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "12345"))

        self.assertEqual(1, len(processed), "the tracker never saw the cancellation")
        self.assertEqual(OrderState.CANCELED, processed[0].new_state)
        self.assertEqual("HBOT-1", processed[0].client_order_id)
        self.assertEqual(OrderState.CANCELED, order.current_state)

    def test_order_on_another_pair_is_not_settled(self):
        """A venue id is not unique across pairs; only the named order may move."""

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"status": "ok", "response": {"data": {"statuses": ["success"]}}}

        async def fake_post(path_url, data=None, is_auth_required=False, **kwargs):
            return {"status": "ok", "response": {"data": {"statuses": ["success"]}}}

        order = InFlightOrder(
            client_order_id="HBOT-2",
            trading_pair="ETH-USDT",
            order_type=OrderType.LIMIT,
            trade_type=TradeType.BUY,
            amount=Decimal("1"),
            price=Decimal("100"),
            creation_timestamp=1.0,
            exchange_order_id="12345",
        )
        self.exchange.in_flight_orders[order.client_order_id] = order

        processed = []
        with (
            patch.object(self.exchange, "exchange_symbol_associated_to_pair",
                         AsyncMock(return_value="BTC")),

            patch.object(self.exchange, "_api_post", side_effect=fake_post),
            patch.object(
                self.exchange._order_tracker,
                "process_order_update",
                side_effect=lambda update: processed.append(update) or True,
            ),
        ):
            self._run(self.exchange.cancel_by_exchange_order_id("BTC-USDT", "12345"))

        self.assertEqual([], processed, "cancelling on BTC-USDT settled an ETH-USDT order")
        self.assertIn("HBOT-2", self.exchange.in_flight_orders)

    def test_signing_keeps_the_venue_id_cancel_flavour(self):
        """The request must be signed as `cancel` with an `oid`, not `cancelByCloid`.

        Signing rewrites the action before it is sent, so asserting only that
        `_api_post` received an `oid` would miss the defect entirely: the payload
        actually submitted carried a `cloid` key and no venue id.
        """
        from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import (
            HyperliquidAuth,
        )

        captured = {}

        def fake_sign(wallet, action, vault, ts, is_mainnet):
            captured["action"] = action
            return "0xsig"

        with patch.object(HyperliquidAuth, "sign_l1_action", side_effect=fake_sign):
            self.exchange._auth._sign_cancel_params(
                {"type": "cancel", "cancels": {"asset": 3, "oid": 12345}},
                "https://api.hyperliquid.xyz",
                1,
            )

        self.assertEqual("cancel", captured["action"]["type"])
        self.assertEqual([{"asset": 3, "oid": 12345}], captured["action"]["cancels"])

    def test_signing_offers_a_cloid_cancel_too(self):
        from hummingbot.connector.derivative.hyperliquid_perpetual.hyperliquid_perpetual_auth import (
            HyperliquidAuth,
        )

        captured = {}

        def fake_sign(wallet, action, vault, ts, is_mainnet):
            captured["action"] = action
            return "0xsig"

        with patch.object(HyperliquidAuth, "sign_l1_action", side_effect=fake_sign):
            self.exchange._auth._sign_cancel_params(
                {"type": "cancelByCloid", "cancels": {"asset": 3, "cloid": "0xabc"}},
                "https://api.hyperliquid.xyz",
                1,
            )

        self.assertEqual("cancelByCloid", captured["action"]["type"])
        self.assertEqual([{"asset": 3, "cloid": "0xabc"}], captured["action"]["cancels"])

if __name__ == "__main__":
    unittest.main()

    unittest.main()
