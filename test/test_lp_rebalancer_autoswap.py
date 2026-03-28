"""
Test autoswap logic in LP Rebalancer controller.
"""
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from hummingbot.core.data_type.common import TradeType
from hummingbot.strategy_v2.executors.swap_executor.data_types import SwapExecutorConfig


class TestLPRebalancerAutoswap(unittest.TestCase):
    """Test the autoswap calculation logic."""

    def setUp(self):
        """Set up test fixtures."""
        # Import here to avoid import errors during collection
        from controllers.generic.lp_rebalancer.lp_rebalancer import LPRebalancer, LPRebalancerConfig

        self.config = LPRebalancerConfig(
            id="test",
            controller_name="lp_rebalancer",
            controller_type="generic",
            connector_name="meteora/clmm",
            network="solana-mainnet-beta",
            trading_pair="SOL-USDC",
            pool_address="test_pool",
            total_amount_quote=Decimal("100"),
            side=1,  # BUY
            position_offset_pct=Decimal("0.5"),
            autoswap=True,
            swap_buffer_pct=Decimal("0.01"),
        )

        # Mock market data provider
        self.mock_market_data_provider = MagicMock()
        self.mock_market_data_provider.time.return_value = 1234567890.0

        # Create controller with mocked dependencies
        with patch.object(LPRebalancer, '__init__', lambda x, y, *args, **kwargs: None):
            self.controller = LPRebalancer(self.config)
            self.controller.config = self.config
            self.controller.market_data_provider = self.mock_market_data_provider
            self.controller._base_token = "SOL"
            self.controller._quote_token = "USDC"
            self.controller._pool_price = Decimal("140")
            # Initialize instance variables that would be set in __init__
            self.controller._last_closed_base_amount = None
            self.controller._last_closed_quote_amount = None
            self.controller._last_closed_base_fee = None
            self.controller._last_closed_quote_fee = None

    def test_positive_offset_no_swap_needed(self):
        """Test that positive offset with sufficient balance doesn't trigger swap."""
        # Side=1 (BUY) with positive offset needs only quote
        self.config.position_offset_pct = Decimal("0.5")
        self.config.side = 1

        # User has enough quote (100 USDC needed, have 150)
        self.mock_market_data_provider.get_balance.side_effect = lambda conn, token: (
            Decimal("0") if token == "SOL" else Decimal("150")
        )

        result = self.controller._check_autoswap_needed(1, Decimal("140"))
        self.assertIsNone(result)  # No swap needed

    def test_positive_offset_swap_needed_for_deficit(self):
        """Test that positive offset with insufficient balance triggers swap."""
        self.config.position_offset_pct = Decimal("0.5")
        self.config.side = 1

        # User has insufficient quote (100 USDC needed, have 50)
        # But has excess base (can sell to get quote)
        self.mock_market_data_provider.get_balance.side_effect = lambda conn, token: (
            Decimal("1.0") if token == "SOL" else Decimal("50")
        )

        # This should NOT trigger swap because we need quote but have base deficit
        # Actually wait - we have base=1.0 SOL but need base=0 for side=1
        # So base_deficit = 0 - 1.0 = -1.0 (have excess)
        # quote_deficit = 100 - 50 = 50 (need more)
        # This matches: quote_deficit > 0 AND base_deficit <= 0 → SELL base

        result = self.controller._check_autoswap_needed(1, Decimal("140"))
        self.assertIsNotNone(result)
        self.assertEqual(result.side, TradeType.SELL)

    def test_negative_offset_triggers_swap_for_buy(self):
        """Test that negative offset triggers swap to get base for BUY side."""
        self.config.position_offset_pct = Decimal("-0.5")  # Negative = in-range
        self.config.side = 1
        self.config.swap_buffer_pct = Decimal("0.01")

        # User has quote (for BUY), needs to swap some to base for in-range portion
        self.mock_market_data_provider.get_balance.side_effect = lambda conn, token: (
            Decimal("0") if token == "SOL" else Decimal("150")
        )

        result = self.controller._check_autoswap_needed(1, Decimal("140"))

        self.assertIsNotNone(result)
        self.assertIsInstance(result, SwapExecutorConfig)
        self.assertEqual(result.side, TradeType.BUY)

        # Swap amount = deficit * (1 + buffer)
        # Required base = 0.5% of 100 / 140 = 0.00357
        # Deficit = 0.00357 - 0 = 0.00357
        # Swap = 0.00357 * 1.0001 ≈ 0.003571
        in_range_pct = Decimal("0.5") / Decimal("100")
        required_base = (Decimal("100") * in_range_pct) / Decimal("140")
        buffer_multiplier = Decimal("1") + (Decimal("0.01") / Decimal("100"))
        expected_amount = required_base * buffer_multiplier
        self.assertAlmostEqual(float(result.amount), float(expected_amount), places=6)

    def test_negative_offset_triggers_swap_for_sell(self):
        """Test that negative offset triggers swap to get quote for SELL side."""
        self.config.position_offset_pct = Decimal("-0.5")  # Negative = in-range
        self.config.side = 2
        self.config.swap_buffer_pct = Decimal("0.01")

        # User has base (for SELL), needs to swap some to quote for in-range portion
        self.mock_market_data_provider.get_balance.side_effect = lambda conn, token: (
            Decimal("1.0") if token == "SOL" else Decimal("0")
        )

        result = self.controller._check_autoswap_needed(2, Decimal("140"))

        self.assertIsNotNone(result)
        self.assertIsInstance(result, SwapExecutorConfig)
        self.assertEqual(result.side, TradeType.SELL)

        # Swap amount = deficit (in base) * (1 + buffer)
        # Required quote = 0.5% of 100 = 0.5 USDC
        # Deficit in base = 0.5 / 140 = 0.00357
        # Swap = 0.00357 * 1.0001 ≈ 0.003571
        in_range_pct = Decimal("0.5") / Decimal("100")
        quote_deficit = Decimal("100") * in_range_pct  # 0.5 USDC
        base_to_sell = quote_deficit / Decimal("140")
        buffer_multiplier = Decimal("1") + (Decimal("0.01") / Decimal("100"))
        expected_amount = base_to_sell * buffer_multiplier
        self.assertAlmostEqual(float(result.amount), float(expected_amount), places=6)

    def test_calculate_amounts_positive_offset_buy(self):
        """Test amount calculation for BUY with positive offset (out-of-range)."""
        self.config.position_offset_pct = Decimal("0.5")
        self.config.side = 1

        base_amt, quote_amt = self.controller._calculate_amounts(1, Decimal("140"))

        # Out-of-range BUY: only needs quote
        self.assertEqual(base_amt, Decimal("0"))
        self.assertEqual(quote_amt, Decimal("100"))

    def test_calculate_amounts_negative_offset_buy(self):
        """Test amount calculation for BUY with negative offset (in-range)."""
        self.config.position_offset_pct = Decimal("-0.5")
        self.config.side = 1

        base_amt, quote_amt = self.controller._calculate_amounts(1, Decimal("140"))

        # In-range BUY: needs both tokens, split based on offset
        # base = 0.5% of 100 / 140 = 0.5 / 140 ≈ 0.00357
        # quote = 99.5% of 100 = 99.5
        in_range_pct = Decimal("0.5") / Decimal("100")
        expected_base = (Decimal("100") * in_range_pct) / Decimal("140")
        expected_quote = Decimal("100") * (Decimal("1") - in_range_pct)

        self.assertAlmostEqual(float(base_amt), float(expected_base), places=6)
        self.assertAlmostEqual(float(quote_amt), float(expected_quote), places=6)

    def test_calculate_amounts_negative_offset_sell(self):
        """Test amount calculation for SELL with negative offset (in-range)."""
        self.config.position_offset_pct = Decimal("-0.5")
        self.config.side = 2

        base_amt, quote_amt = self.controller._calculate_amounts(2, Decimal("140"))

        # In-range SELL: needs both tokens
        # quote = 0.5% of 100 = 0.5
        # base = 99.5% of 100 / 140 ≈ 0.7107
        in_range_pct = Decimal("0.5") / Decimal("100")
        expected_quote = Decimal("100") * in_range_pct
        expected_base = (Decimal("100") * (Decimal("1") - in_range_pct)) / Decimal("140")

        self.assertAlmostEqual(float(base_amt), float(expected_base), places=6)
        self.assertAlmostEqual(float(quote_amt), float(expected_quote), places=6)

    def test_negative_offset_insufficient_balance(self):
        """Test that negative offset with insufficient balance logs warning."""
        self.config.position_offset_pct = Decimal("-0.5")
        self.config.side = 1

        # User has insufficient quote to swap
        self.mock_market_data_provider.get_balance.side_effect = lambda conn, token: (
            Decimal("0") if token == "SOL" else Decimal("0.1")  # Very little quote
        )

        result = self.controller._check_autoswap_needed(1, Decimal("140"))
        self.assertIsNone(result)  # Should return None due to insufficient balance


if __name__ == "__main__":
    unittest.main()
