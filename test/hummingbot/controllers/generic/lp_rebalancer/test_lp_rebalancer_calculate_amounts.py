import asyncio
import unittest
from decimal import Decimal
from unittest.mock import MagicMock

from controllers.generic.lp_rebalancer.lp_rebalancer import LPRebalancer, LPRebalancerConfig
from hummingbot.data_feed.market_data_provider import MarketDataProvider


def _make_controller(total_amount_quote: Decimal = Decimal("100")) -> LPRebalancer:
    """Helper: build an LPRebalancer with a mocked market_data_provider."""
    config = LPRebalancerConfig(
        id="test_controller",
        connector_name="meteora/clmm",
        network="solana-mainnet-beta",
        trading_pair="SOL-USDC",
        pool_address="test_pool",
        total_amount_quote=total_amount_quote,
        side=1,
    )
    mock_market_data_provider = MagicMock(spec=MarketDataProvider)
    mock_actions_queue = MagicMock(spec=asyncio.Queue)

    controller = LPRebalancer(
        config=config,
        market_data_provider=mock_market_data_provider,
        actions_queue=mock_actions_queue,
    )
    return controller


class TestCalculateAmountsBalanceClamping(unittest.TestCase):
    """
    Unit tests for LPRebalancer._calculate_amounts balance-clamping logic.

    Covers the change introduced in commit 9e26574:
      "feat: clamp total amount to available balance to prevent order failures"
    """

    # ------------------------------------------------------------------
    # Side 1 (BUY) – quote token clamping
    # ------------------------------------------------------------------

    def test_buy_no_clamping_when_balance_sufficient(self):
        """Side 1: balance >= total → amounts unchanged."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        controller.market_data_provider.get_balance.return_value = Decimal("150")

        price = Decimal("100")
        base_amt, quote_amt = controller._calculate_amounts(side=1, current_price=price)

        self.assertEqual(quote_amt, Decimal("100"))
        self.assertEqual(base_amt, Decimal("0"))

    def test_buy_clamped_when_balance_less_than_total(self):
        """Side 1: balance < total → quote_amt is clamped to available balance."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        controller.market_data_provider.get_balance.return_value = Decimal("80")

        base_amt, quote_amt = controller._calculate_amounts(side=1, current_price=Decimal("100"))

        self.assertEqual(quote_amt, Decimal("80"))
        self.assertEqual(base_amt, Decimal("0"))

    def test_buy_no_clamping_when_balance_is_none(self):
        """Side 1: get_balance returns None → use configured total (no crash)."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        controller.market_data_provider.get_balance.return_value = None

        base_amt, quote_amt = controller._calculate_amounts(side=1, current_price=Decimal("100"))

        self.assertEqual(quote_amt, Decimal("100"))
        self.assertEqual(base_amt, Decimal("0"))

    def test_buy_no_clamping_when_balance_exactly_equals_total(self):
        """Side 1: balance == total → no clamping, use total as-is."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        controller.market_data_provider.get_balance.return_value = Decimal("100")

        base_amt, quote_amt = controller._calculate_amounts(side=1, current_price=Decimal("100"))

        self.assertEqual(quote_amt, Decimal("100"))
        self.assertEqual(base_amt, Decimal("0"))

    # ------------------------------------------------------------------
    # Side 2 (SELL) – base token clamping
    # ------------------------------------------------------------------

    def test_sell_no_clamping_when_base_value_sufficient(self):
        """Side 2: available_base * price >= total → amounts unchanged."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        # 2 SOL * 100 USDC/SOL = 200 USDC >= 100 USDC → no clamping
        controller.market_data_provider.get_balance.return_value = Decimal("2")

        price = Decimal("100")
        base_amt, quote_amt = controller._calculate_amounts(side=2, current_price=price)

        self.assertEqual(quote_amt, Decimal("0"))
        # base_amt = total / price = 100 / 100 = 1
        self.assertEqual(base_amt, Decimal("1"))

    def test_sell_clamped_when_base_value_less_than_total(self):
        """Side 2: available_base * price < total → base_amt is clamped."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        # Only 0.5 SOL available → 0.5 * 100 = 50 USDC equivalent
        controller.market_data_provider.get_balance.return_value = Decimal("0.5")

        price = Decimal("100")
        base_amt, quote_amt = controller._calculate_amounts(side=2, current_price=price)

        # total clamped to 50, base_amt = 50 / 100 = 0.5
        self.assertEqual(quote_amt, Decimal("0"))
        self.assertEqual(base_amt, Decimal("0.5"))

    def test_sell_no_clamping_when_balance_is_none(self):
        """Side 2: get_balance returns None → use configured total (no crash)."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        controller.market_data_provider.get_balance.return_value = None

        price = Decimal("100")
        base_amt, quote_amt = controller._calculate_amounts(side=2, current_price=price)

        self.assertEqual(quote_amt, Decimal("0"))
        self.assertEqual(base_amt, Decimal("1"))  # 100 / 100

    # ------------------------------------------------------------------
    # Side 0 (BOTH) – no balance check, 50/50 split
    # ------------------------------------------------------------------

    def test_both_splits_50_50_no_balance_check(self):
        """Side 0: no balance clamping, splits total 50/50 into quote and base."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        # get_balance should NOT be called for side 0
        controller.market_data_provider.get_balance.return_value = Decimal("10")

        price = Decimal("100")
        base_amt, quote_amt = controller._calculate_amounts(side=0, current_price=price)

        # quote = 100/2 = 50, base = 50/100 = 0.5
        self.assertEqual(quote_amt, Decimal("50"))
        self.assertEqual(base_amt, Decimal("0.5"))
        controller.market_data_provider.get_balance.assert_not_called()

    # ------------------------------------------------------------------
    # Exception safety
    # ------------------------------------------------------------------

    def test_exception_in_get_balance_falls_back_to_total(self):
        """If get_balance raises, the configured total is used unchanged (no crash)."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        controller.market_data_provider.get_balance.side_effect = RuntimeError("provider unavailable")

        # Should NOT raise; falls back to original total
        base_amt, quote_amt = controller._calculate_amounts(side=1, current_price=Decimal("100"))

        self.assertEqual(quote_amt, Decimal("100"))
        self.assertEqual(base_amt, Decimal("0"))

    def test_exception_in_get_balance_sell_falls_back_to_total(self):
        """Side 2: exception in get_balance → use configured total (no crash)."""
        controller = _make_controller(total_amount_quote=Decimal("100"))
        controller.market_data_provider.get_balance.side_effect = RuntimeError("provider unavailable")

        base_amt, quote_amt = controller._calculate_amounts(side=2, current_price=Decimal("100"))

        self.assertEqual(quote_amt, Decimal("0"))
        self.assertEqual(base_amt, Decimal("1"))  # 100 / 100

    # ------------------------------------------------------------------
    # Token routing: correct token is queried
    # ------------------------------------------------------------------

    def test_buy_queries_quote_token(self):
        """Side 1: get_balance is called with (connector_name, quote_token)."""
        controller = _make_controller()
        controller.market_data_provider.get_balance.return_value = Decimal("200")

        controller._calculate_amounts(side=1, current_price=Decimal("100"))

        controller.market_data_provider.get_balance.assert_called_once_with(
            "meteora/clmm", "USDC"
        )

    def test_sell_queries_base_token(self):
        """Side 2: get_balance is called with (connector_name, base_token)."""
        controller = _make_controller()
        controller.market_data_provider.get_balance.return_value = Decimal("5")

        controller._calculate_amounts(side=2, current_price=Decimal("100"))

        controller.market_data_provider.get_balance.assert_called_once_with(
            "meteora/clmm", "SOL"
        )


if __name__ == "__main__":
    unittest.main()
