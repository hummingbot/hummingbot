"""Tests for Backpack utilities."""
import unittest

from hummingbot.connector.exchange.backpack.backpack_utils import (
    convert_order_side,
    convert_order_type,
    convert_time_in_force,
    get_backpack_trading_pair,
    get_hummingbot_trading_pair,
    parse_backpack_symbol,
)
from hummingbot.core.data_type.common import OrderType, TradeType


class TestBackpackUtils(unittest.TestCase):
    """Test cases for Backpack utilities."""

    def test_get_backpack_trading_pair(self):
        """Test conversion from Hummingbot to Backpack trading pair."""
        self.assertEqual(get_backpack_trading_pair("SOL-USDC"), "SOL_USDC")
        self.assertEqual(get_backpack_trading_pair("BTC-USDT"), "BTC_USDT")

    def test_get_hummingbot_trading_pair(self):
        """Test conversion from Backpack to Hummingbot trading pair."""
        self.assertEqual(get_hummingbot_trading_pair("SOL_USDC"), "SOL-USDC")
        self.assertEqual(get_hummingbot_trading_pair("BTC_USDT"), "BTC-USDT")

    def test_get_hummingbot_trading_pair_empty(self):
        """Test conversion with empty string."""
        self.assertIsNone(get_hummingbot_trading_pair(""))
        self.assertIsNone(get_hummingbot_trading_pair(None))

    def test_convert_order_side_buy(self):
        """Test conversion of BUY trade type."""
        self.assertEqual(convert_order_side(TradeType.BUY), "Bid")

    def test_convert_order_side_sell(self):
        """Test conversion of SELL trade type."""
        self.assertEqual(convert_order_side(TradeType.SELL), "Ask")

    def test_convert_order_type_limit(self):
        """Test conversion of LIMIT order type."""
        self.assertEqual(convert_order_type(OrderType.LIMIT), "Limit")
        self.assertEqual(convert_order_type(OrderType.LIMIT_MAKER), "Limit")

    def test_convert_order_type_market(self):
        """Test conversion of MARKET order type."""
        self.assertEqual(convert_order_type(OrderType.MARKET), "Market")

    def test_convert_time_in_force_gtc(self):
        """Test conversion of GTC time in force."""
        self.assertEqual(convert_time_in_force("GTC"), "GTC")

    def test_convert_time_in_force_ioc(self):
        """Test conversion of IOC time in force."""
        self.assertEqual(convert_time_in_force("IOC"), "IOC")

    def test_convert_time_in_force_fok(self):
        """Test conversion of FOK time in force."""
        self.assertEqual(convert_time_in_force("FOK"), "FOK")

    def test_convert_time_in_force_default(self):
        """Test default time in force conversion."""
        self.assertEqual(convert_time_in_force("UNKNOWN"), "GTC")

    def test_parse_backpack_symbol(self):
        """Test parsing of Backpack symbol."""
        base, quote = parse_backpack_symbol("SOL_USDC")
        self.assertEqual(base, "SOL")
        self.assertEqual(quote, "USDC")

    def test_parse_backpack_symbol_invalid(self):
        """Test parsing of invalid Backpack symbol."""
        with self.assertRaises(ValueError):
            parse_backpack_symbol("INVALID")


if __name__ == "__main__":
    unittest.main()
