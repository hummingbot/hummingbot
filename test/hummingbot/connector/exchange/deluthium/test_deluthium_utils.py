"""
Unit tests for Deluthium utilities.
"""

import unittest
from decimal import Decimal

from hummingbot.connector.exchange.deluthium import deluthium_utils as utils
from hummingbot.connector.exchange.deluthium import deluthium_constants as CONSTANTS


class TestDeluthiumUtils(unittest.TestCase):
    """Test cases for Deluthium utility functions."""

    def test_to_wei_18_decimals(self):
        """Test converting to wei with 18 decimals."""
        amount = Decimal("1.5")
        result = utils.to_wei(amount, 18)
        self.assertEqual(result, "1500000000000000000")

    def test_to_wei_6_decimals(self):
        """Test converting to wei with 6 decimals (USDT/USDC)."""
        amount = Decimal("100")
        result = utils.to_wei(amount, 6)
        self.assertEqual(result, "100000000")

    def test_from_wei_18_decimals(self):
        """Test converting from wei with 18 decimals."""
        wei_amount = "1500000000000000000"
        result = utils.from_wei(wei_amount, 18)
        self.assertEqual(result, Decimal("1.5"))

    def test_from_wei_6_decimals(self):
        """Test converting from wei with 6 decimals."""
        wei_amount = "100000000"
        result = utils.from_wei(wei_amount, 6)
        self.assertEqual(result, Decimal("100"))

    def test_convert_symbol_to_hummingbot(self):
        """Test converting Deluthium symbol to Hummingbot format."""
        self.assertEqual(
            utils.convert_symbol_to_hummingbot("WBNB-USDT"),
            "WBNB/USDT"
        )
        self.assertEqual(
            utils.convert_symbol_to_hummingbot("WETH-USDC"),
            "WETH/USDC"
        )

    def test_convert_symbol_to_deluthium(self):
        """Test converting Hummingbot symbol to Deluthium format."""
        self.assertEqual(
            utils.convert_symbol_to_deluthium("WBNB/USDT"),
            "WBNB-USDT"
        )
        self.assertEqual(
            utils.convert_symbol_to_deluthium("WETH/USDC"),
            "WETH-USDC"
        )

    def test_is_exchange_information_valid_enabled(self):
        """Test validation of enabled pair."""
        pair_info = {"is_enabled": True, "pair_symbol": "WBNB-USDT"}
        self.assertTrue(utils.is_exchange_information_valid(pair_info))

    def test_is_exchange_information_valid_disabled(self):
        """Test validation of disabled pair."""
        pair_info = {"is_enabled": False, "pair_symbol": "WBNB-USDT"}
        self.assertFalse(utils.is_exchange_information_valid(pair_info))

    def test_is_exchange_information_valid_default(self):
        """Test validation when is_enabled is not present (defaults to True)."""
        pair_info = {"pair_symbol": "WBNB-USDT"}
        self.assertTrue(utils.is_exchange_information_valid(pair_info))

    def test_get_wrapped_token_bsc(self):
        """Test getting wrapped token for BSC."""
        wrapped = utils.get_wrapped_token(56)
        self.assertEqual(
            wrapped,
            "0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
        )

    def test_get_wrapped_token_base(self):
        """Test getting wrapped token for Base."""
        wrapped = utils.get_wrapped_token(8453)
        self.assertEqual(
            wrapped,
            "0x4200000000000000000000000000000000000006"
        )

    def test_get_wrapped_token_ethereum(self):
        """Test getting wrapped token for Ethereum."""
        wrapped = utils.get_wrapped_token(1)
        self.assertEqual(
            wrapped,
            "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
        )

    def test_get_wrapped_token_unsupported(self):
        """Test getting wrapped token for unsupported chain."""
        wrapped = utils.get_wrapped_token(999)
        self.assertIsNone(wrapped)

    def test_is_native_token_true(self):
        """Test native token detection with zero address."""
        self.assertTrue(utils.is_native_token(CONSTANTS.NATIVE_TOKEN_ADDRESS))
        self.assertTrue(
            utils.is_native_token("0x0000000000000000000000000000000000000000")
        )

    def test_is_native_token_false(self):
        """Test native token detection with non-zero address."""
        self.assertFalse(
            utils.is_native_token("0xBB4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c")
        )

    def test_validate_chain_id_valid(self):
        """Test chain ID validation with valid IDs."""
        self.assertEqual(utils.validate_chain_id(56), 56)
        self.assertEqual(utils.validate_chain_id(8453), 8453)
        self.assertEqual(utils.validate_chain_id(1), 1)

    def test_validate_chain_id_invalid(self):
        """Test chain ID validation with invalid ID."""
        with self.assertRaises(ValueError):
            utils.validate_chain_id(999)


class TestDeluthiumConfigMap(unittest.TestCase):
    """Test cases for DeluthiumConfigMap."""

    def test_config_map_connector_name(self):
        """Test that connector name is correct."""
        self.assertEqual(utils.KEYS.connector, "deluthium")

    def test_default_fees(self):
        """Test default fee schema."""
        self.assertEqual(
            utils.DEFAULT_FEES.maker_percent_fee_decimal,
            Decimal("0")
        )
        self.assertEqual(
            utils.DEFAULT_FEES.taker_percent_fee_decimal,
            Decimal("0.001")
        )

    def test_centralized_flag(self):
        """Test that CENTRALIZED is False (DEX)."""
        self.assertFalse(utils.CENTRALIZED)


if __name__ == "__main__":
    unittest.main()
