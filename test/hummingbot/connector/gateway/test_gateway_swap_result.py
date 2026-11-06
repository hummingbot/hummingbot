import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from hummingbot.connector.gateway.gateway import Gateway
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.in_flight_order import OrderState


class GatewayStoreSwapResultTests(unittest.TestCase):
    """_store_swap_result must report the amounts that actually moved on-chain.

    Gateway's `amountIn`/`amountOut` come from the wallet's pre/post token balance
    deltas for the settled transaction. Reporting the requested amount instead
    overstates the fill, and callers that spend the proceeds downstream (an LP
    open's base_amount) then ask the chain for tokens that were never received.
    """

    ORDER_ID = "order-1"
    TX_HASH = "sig-1"
    PAIR = "ANSEM-SOL"

    def setUp(self):
        self.connector = Gateway.__new__(Gateway)
        self.connector._native_currency = "SOL"
        self.connector._order_tracker = MagicMock()

        # The order was placed for 62 base tokens.
        self.tracked_order = MagicMock()
        self.tracked_order.amount = Decimal("62")
        self.connector._order_tracker.fetch_order.return_value = self.tracked_order

        patcher = unittest.mock.patch.object(
            Gateway, "current_timestamp", new_callable=unittest.mock.PropertyMock, return_value=1234.0
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _store(self, trade_type, data, status=1):
        self.connector._store_swap_result(
            order_id=self.ORDER_ID,
            trade_type=trade_type,
            trading_pair=self.PAIR,
            amount=Decimal("62"),
            order_result={"status": status, "data": data},
            transaction_hash=self.TX_HASH,
        )

    def _trade_update(self):
        self.connector._order_tracker.process_trade_update.assert_called_once()
        return self.connector._order_tracker.process_trade_update.call_args[0][0]

    def test_buy_fill_uses_realized_amount_not_requested(self):
        """A BUY receives base as amountOut - slippage means it is under the request."""
        self._store(TradeType.BUY, {"amountIn": "0.5", "amountOut": "61.962753", "fee": "0.000005"})

        trade_update = self._trade_update()
        self.assertEqual(trade_update.fill_base_amount, Decimal("61.962753"))
        self.assertNotEqual(trade_update.fill_base_amount, self.tracked_order.amount)
        self.assertEqual(trade_update.fill_quote_amount, Decimal("0.5"))

    def test_sell_fill_uses_realized_amount(self):
        """A SELL sends base as amountIn and receives quote as amountOut."""
        self._store(TradeType.SELL, {"amountIn": "61.9", "amountOut": "0.497", "fee": "0.000005"})

        trade_update = self._trade_update()
        self.assertEqual(trade_update.fill_base_amount, Decimal("61.9"))
        self.assertEqual(trade_update.fill_quote_amount, Decimal("0.497"))

    def test_fill_quote_amount_is_not_rederived_from_price(self):
        """Both legs come straight from Gateway, so no rounding drift is introduced."""
        self._store(TradeType.BUY, {"amountIn": "0.3", "amountOut": "7", "fee": "0"})

        trade_update = self._trade_update()
        self.assertEqual(trade_update.fill_quote_amount, Decimal("0.3"))
        # Re-deriving as base * price would give 7 * (0.3/7) with Decimal rounding.
        self.assertEqual(trade_update.fill_price, Decimal("0.3") / Decimal("7"))

    def test_usdc_quote_buy_maps_by_side_not_by_token(self):
        """Base/quote are assigned from the trade side, so any quote asset works.

        Here both legs are SPL tokens (memecoin/USDC) rather than the memecoin/SOL
        shape above - the mapping must be identical.
        """
        self.connector._store_swap_result(
            order_id=self.ORDER_ID,
            trade_type=TradeType.BUY,
            trading_pair="ANSEM-USDC",
            amount=Decimal("62"),
            order_result={"status": 1, "data": {"amountIn": "40.25", "amountOut": "61.962753", "fee": "0.000005"}},
            transaction_hash=self.TX_HASH,
        )

        trade_update = self._trade_update()
        self.assertEqual(trade_update.fill_base_amount, Decimal("61.962753"))
        self.assertEqual(trade_update.fill_quote_amount, Decimal("40.25"))

    def test_usdc_quote_sell_maps_by_side_not_by_token(self):
        self.connector._store_swap_result(
            order_id=self.ORDER_ID,
            trade_type=TradeType.SELL,
            trading_pair="ANSEM-USDC",
            amount=Decimal("62"),
            order_result={"status": 1, "data": {"amountIn": "61.9", "amountOut": "40.1", "fee": "0.000005"}},
            transaction_hash=self.TX_HASH,
        )

        trade_update = self._trade_update()
        self.assertEqual(trade_update.fill_base_amount, Decimal("61.9"))
        self.assertEqual(trade_update.fill_quote_amount, Decimal("40.1"))

    def test_fee_asset_is_native_currency_not_the_quote(self):
        """Gas is always paid in SOL even when the pair is quoted in USDC."""
        self.connector._store_swap_result(
            order_id=self.ORDER_ID,
            trade_type=TradeType.BUY,
            trading_pair="ANSEM-USDC",
            amount=Decimal("62"),
            order_result={"status": 1, "data": {"amountIn": "40.25", "amountOut": "61.9", "fee": "0.000005"}},
            transaction_hash=self.TX_HASH,
        )

        trade_update = self._trade_update()
        self.assertEqual(trade_update.fee.flat_fees[0].token, "SOL")
        self.assertEqual(trade_update.fee.flat_fees[0].amount, Decimal("0.000005"))

    def test_unconfirmed_swap_is_not_marked_filled(self):
        """No realized amounts means the swap has not settled - leave the order open.

        Previously this produced a phantom 0-amount fill at price 0 and still
        forced the order to FILLED.
        """
        self._store(TradeType.BUY, {}, status=0)

        self.connector._order_tracker.process_trade_update.assert_not_called()
        self.connector._order_tracker.process_order_update.assert_not_called()

    def test_confirmed_swap_is_marked_filled(self):
        self._store(TradeType.BUY, {"amountIn": "0.5", "amountOut": "61.9", "fee": "0"})

        self.connector._order_tracker.process_order_update.assert_called_once()
        order_update = self.connector._order_tracker.process_order_update.call_args[0][0]
        self.assertEqual(order_update.new_state, OrderState.FILLED)


if __name__ == "__main__":
    unittest.main()
