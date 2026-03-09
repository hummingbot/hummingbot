"""
Tests for Bluefin Perpetual utility functions.

Tests configuration validation, fee structures, and utility helpers.
"""
import unittest
from decimal import Decimal

from hummingbot.connector.derivative.bluefin_perpetual.bluefin_perpetual_utils import (
    CENTRALIZED,
    DEFAULT_FEES,
    EXAMPLE_PAIR,
    BluefinPerpetualConfigMap,
)


class BluefinPerpetualUtilsTests(unittest.TestCase):
    """Test suite for Bluefin Perpetual utility functions."""

    def test_centralized_constant(self):
        """Test that CENTRALIZED is set to False (Bluefin is decentralized)."""
        self.assertFalse(CENTRALIZED)

    def test_example_pair(self):
        """Test that EXAMPLE_PAIR is properly set."""
        self.assertEqual("BTC-USD", EXAMPLE_PAIR)

    def test_default_fees_structure(self):
        """Test that DEFAULT_FEES are properly configured."""
        # Verify fee schema exists
        self.assertIsNotNone(DEFAULT_FEES)

        # Verify maker fee (0.01%)
        maker_fee = DEFAULT_FEES.maker_percent_fee_decimal
        self.assertEqual(Decimal("0.0001"), maker_fee)

        # Verify taker fee (0.05%)
        taker_fee = DEFAULT_FEES.taker_percent_fee_decimal
        self.assertEqual(Decimal("0.0005"), taker_fee)

        # Verify buy percent fee deducted from returns
        self.assertTrue(DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_config_map_has_required_fields(self):
        """Test that BluefinPerpetualConfigMap has all required fields."""
        # Should be able to create config with all required fields
        config = BluefinPerpetualConfigMap.model_construct(
            bluefin_perpetual_wallet_mnemonic="test " * 23 + "word",
            bluefin_perpetual_network="MAINNET",
        )

        self.assertEqual("bluefin_perpetual", config.connector)
        self.assertIsNotNone(config.bluefin_perpetual_wallet_mnemonic)
        self.assertEqual("MAINNET", config.bluefin_perpetual_network)

    def test_config_map_network_options(self):
        """Test that network field accepts both MAINNET and STAGING."""
        # Test MAINNET
        config_mainnet = BluefinPerpetualConfigMap.model_construct(
            bluefin_perpetual_wallet_mnemonic="test " * 23 + "word",
            bluefin_perpetual_network="MAINNET",
        )
        self.assertEqual("MAINNET", config_mainnet.bluefin_perpetual_network)

        # Test STAGING
        config_staging = BluefinPerpetualConfigMap.model_construct(
            bluefin_perpetual_wallet_mnemonic="test " * 23 + "word",
            bluefin_perpetual_network="STAGING",
        )
        self.assertEqual("STAGING", config_staging.bluefin_perpetual_network)

    def test_config_map_title(self):
        """Test that config map has proper title."""
        config = BluefinPerpetualConfigMap.model_construct(
            bluefin_perpetual_wallet_mnemonic="test " * 23 + "word",
            bluefin_perpetual_network="MAINNET",
        )
        self.assertEqual("bluefin_perpetual", config.model_config.get("title"))
