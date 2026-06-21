"""
Test DCA amount validation in DMAN controllers.
Tests for ZeroDivisionError fix when dca_amounts or dca_amounts_pct sum to zero.
"""
import pytest
from decimal import Decimal

from controllers.market_making.dman_maker_v2 import DManMakerV2Config
from controllers.directional_trading.dman_v3 import DManV3ControllerConfig


class TestDManMakerV2Validation:
    """Test DManMakerV2 config validation for dca_amounts."""

    def test_valid_dca_amounts(self):
        """Test that valid dca_amounts are accepted."""
        config = DManMakerV2Config(
            connector_name="binance",
            trading_pair="BTC-USDT",
            dca_spreads="0.01,0.02,0.04",
            dca_amounts="0.1,0.2,0.4",
        )
        assert config.dca_amounts == [0.1, 0.2, 0.4]

    def test_zero_sum_dca_amounts_raises_error(self):
        """Test that zero sum dca_amounts raises ValueError."""
        with pytest.raises(ValueError, match="sum of dca_amounts cannot be zero"):
            DManMakerV2Config(
                connector_name="binance",
                trading_pair="BTC-USDT",
                dca_spreads="0.01,0.02,0.04",
                dca_amounts="0,0,0",
            )

    def test_negative_dca_amounts_raises_error(self):
        """Test that negative dca_amounts raises ValueError."""
        with pytest.raises(ValueError, match="cannot contain negative values"):
            DManMakerV2Config(
                connector_name="binance",
                trading_pair="BTC-USDT",
                dca_spreads="0.01,0.02,0.04",
                dca_amounts="0.1,-0.2,0.4",
            )

    def test_mismatched_lengths_raises_error(self):
        """Test that mismatched lengths raises ValueError."""
        with pytest.raises(ValueError, match="must match"):
            DManMakerV2Config(
                connector_name="binance",
                trading_pair="BTC-USDT",
                dca_spreads="0.01,0.02,0.04",
                dca_amounts="0.1,0.2",
            )

    def test_empty_dca_amounts_uses_default(self):
        """Test that empty dca_amounts uses default values."""
        config = DManMakerV2Config(
            connector_name="binance",
            trading_pair="BTC-USDT",
            dca_spreads="0.01,0.02,0.04",
            dca_amounts="",
        )
        assert len(config.dca_amounts) == 3


class TestDManV3Validation:
    """Test DManV3ControllerConfig validation for dca_amounts_pct."""

    def test_valid_dca_amounts_pct(self):
        """Test that valid dca_amounts_pct are accepted."""
        config = DManV3ControllerConfig(
            connector_name="binance",
            trading_pair="BTC-USDT",
            dca_spreads="0.001,0.018,0.15,0.25",
            dca_amounts_pct="0.1,0.2,0.3,0.4",
        )
        assert config.dca_amounts_pct == [Decimal('0.1'), Decimal('0.2'), Decimal('0.3'), Decimal('0.4')]

    def test_zero_sum_dca_amounts_pct_raises_error(self):
        """Test that zero sum dca_amounts_pct raises ValueError."""
        with pytest.raises(ValueError, match="sum of dca_amounts_pct cannot be zero"):
            DManV3ControllerConfig(
                connector_name="binance",
                trading_pair="BTC-USDT",
                dca_spreads="0.001,0.018,0.15,0.25",
                dca_amounts_pct="0,0,0,0",
            )

    def test_negative_dca_amounts_pct_raises_error(self):
        """Test that negative dca_amounts_pct raises ValueError."""
        with pytest.raises(ValueError, match="cannot contain negative values"):
            DManV3ControllerConfig(
                connector_name="binance",
                trading_pair="BTC-USDT",
                dca_spreads="0.001,0.018,0.15,0.25",
                dca_amounts_pct="0.1,-0.2,0.3,0.4",
            )

    def test_mismatched_lengths_raises_error(self):
        """Test that mismatched lengths raises ValueError."""
        with pytest.raises(ValueError, match="must have the same length"):
            DManV3ControllerConfig(
                connector_name="binance",
                trading_pair="BTC-USDT",
                dca_spreads="0.001,0.018,0.15,0.25",
                dca_amounts_pct="0.1,0.2",
            )

    def test_empty_dca_amounts_pct_uses_default(self):
        """Test that empty dca_amounts_pct uses default values."""
        config = DManV3ControllerConfig(
            connector_name="binance",
            trading_pair="BTC-USDT",
            dca_spreads="0.001,0.018,0.15,0.25",
            dca_amounts_pct="",
        )
        assert len(config.dca_amounts_pct) == 4
