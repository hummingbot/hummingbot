import unittest
from decimal import Decimal

from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_utils import (
    calculate_liquidation_price,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
    decimal_val_or_none,
    get_position_side_from_direction,
    is_exchange_information_valid,
)


class TestBackpackPerpetualUtils(unittest.TestCase):
    """Test cases for backpack_perpetual_utils module."""

    def test_is_exchange_information_valid_with_valid_list(self):
        """Test validation with valid exchange info list."""
        exchange_info = [{"symbol": "BTC_USDC_PERP", "baseSymbol": "BTC", "quoteSymbol": "USDC"}]
        self.assertTrue(is_exchange_information_valid(exchange_info))

    def test_is_exchange_information_valid_with_empty_list(self):
        """Test validation with empty list."""
        self.assertFalse(is_exchange_information_valid([]))

    def test_is_exchange_information_valid_with_none(self):
        """Test validation with None."""
        self.assertFalse(is_exchange_information_valid(None))

    def test_is_exchange_information_valid_with_dict(self):
        """Test validation with dict instead of list."""
        self.assertFalse(is_exchange_information_valid({"symbol": "BTC_USDC_PERP"}))

    def test_convert_to_exchange_trading_pair_with_hyphen(self):
        """Test conversion from hyphenated format to Backpack perpetual format."""
        result = convert_to_exchange_trading_pair("BTC-USDC")
        self.assertEqual("BTC_USDC_PERP", result)

    def test_convert_to_exchange_trading_pair_already_underscore(self):
        """Test conversion from underscore format (no _PERP suffix)."""
        result = convert_to_exchange_trading_pair("BTC_USDC")
        self.assertEqual("BTC_USDC_PERP", result)

    def test_convert_to_exchange_trading_pair_already_perp(self):
        """Test conversion when already in perpetual format."""
        result = convert_to_exchange_trading_pair("BTC_USDC_PERP")
        self.assertEqual("BTC_USDC_PERP", result)

    def test_convert_from_exchange_trading_pair(self):
        """Test conversion from Backpack perpetual format to hyphenated format."""
        result = convert_from_exchange_trading_pair("BTC_USDC_PERP")
        self.assertEqual("BTC-USDC", result)

    def test_convert_from_exchange_trading_pair_no_perp(self):
        """Test conversion when no _PERP suffix."""
        result = convert_from_exchange_trading_pair("BTC_USDC")
        self.assertEqual("BTC-USDC", result)

    def test_decimal_val_or_none_with_valid_int(self):
        """Test decimal conversion with integer."""
        result = decimal_val_or_none(100)
        self.assertEqual(Decimal("100"), result)

    def test_decimal_val_or_none_with_valid_float(self):
        """Test decimal conversion with float."""
        result = decimal_val_or_none(99.99)
        self.assertEqual(Decimal("99.99"), result)

    def test_decimal_val_or_none_with_valid_string(self):
        """Test decimal conversion with string."""
        result = decimal_val_or_none("12345.67")
        self.assertEqual(Decimal("12345.67"), result)

    def test_decimal_val_or_none_with_none(self):
        """Test decimal conversion with None."""
        result = decimal_val_or_none(None)
        self.assertIsNone(result)

    def test_decimal_val_or_none_with_invalid_string(self):
        """Test decimal conversion with invalid string."""
        result = decimal_val_or_none("not_a_number")
        self.assertIsNone(result)

    def test_get_position_side_from_direction_long(self):
        """Test position side for long direction."""
        result = get_position_side_from_direction("long")
        self.assertEqual("LONG", result)

    def test_get_position_side_from_direction_long_uppercase(self):
        """Test position side for LONG direction (case insensitive)."""
        result = get_position_side_from_direction("LONG")
        self.assertEqual("LONG", result)

    def test_get_position_side_from_direction_short(self):
        """Test position side for short direction."""
        result = get_position_side_from_direction("short")
        self.assertEqual("SHORT", result)

    def test_get_position_side_from_direction_short_uppercase(self):
        """Test position side for SHORT direction (case insensitive)."""
        result = get_position_side_from_direction("SHORT")
        self.assertEqual("SHORT", result)

    def test_calculate_liquidation_price_long(self):
        """Test liquidation price calculation for long position."""
        entry_price = Decimal("50000")
        position_size = Decimal("1")
        margin = Decimal("5000")  # 10x leverage
        is_long = True

        liq_price = calculate_liquidation_price(
            entry_price=entry_price,
            position_size=position_size,
            margin=margin,
            is_long=is_long,
        )

        # For long: liq_price should be below entry price
        self.assertLess(liq_price, entry_price)
        self.assertGreater(liq_price, Decimal("0"))

    def test_calculate_liquidation_price_short(self):
        """Test liquidation price calculation for short position."""
        entry_price = Decimal("50000")
        position_size = Decimal("-1")
        margin = Decimal("5000")  # 10x leverage
        is_long = False

        liq_price = calculate_liquidation_price(
            entry_price=entry_price,
            position_size=position_size,
            margin=margin,
            is_long=is_long,
        )

        # For short: liq_price should be above entry price
        self.assertGreater(liq_price, entry_price)

    def test_calculate_liquidation_price_zero_size(self):
        """Test liquidation price calculation with zero position size."""
        liq_price = calculate_liquidation_price(
            entry_price=Decimal("50000"),
            position_size=Decimal("0"),
            margin=Decimal("5000"),
            is_long=True,
        )
        self.assertEqual(Decimal("0"), liq_price)

    def test_calculate_liquidation_price_zero_margin(self):
        """Test liquidation price calculation with zero margin."""
        liq_price = calculate_liquidation_price(
            entry_price=Decimal("50000"),
            position_size=Decimal("1"),
            margin=Decimal("0"),
            is_long=True,
        )
        self.assertEqual(Decimal("0"), liq_price)


if __name__ == "__main__":
    unittest.main()
