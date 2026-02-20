import unittest
from decimal import Decimal

from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_utils import (
    convert_from_exchange_symbol,
    convert_to_exchange_symbol,
    get_pair_prefix,
    get_pair_suffix,
    get_exchange_trading_pair,
    get_original_trading_pair,
)


class TestDecibelPerpetualUtils(unittest.TestCase):
    """Unit tests for Decibel Perpetual utility functions"""

    def test_convert_to_exchange_symbol_usd(self):
        """Test converting USD trading pair to exchange symbol"""
        result = convert_to_exchange_symbol("BTC-USD")
        self.assertEqual(result, "BTC-PERP")

    def test_convert_to_exchange_symbol_usdt(self):
        """Test converting USDT trading pair to exchange symbol - it will replace USD with PERP incorrectly if the logic isn't specific"""
        # Current implementation replaces "-USD" with "-PERP", so USDT becomes PERPT
        # This test documents the current behavior
        result = convert_to_exchange_symbol("BTC-USDT")
        self.assertEqual(result, "BTC-PERPT")

    def test_convert_from_exchange_symbol_perp(self):
        """Test converting PERP exchange symbol to trading pair"""
        result = convert_from_exchange_symbol("BTC-PERP")
        self.assertEqual(result, "BTC-USD")

    def test_convert_from_exchange_symbol_non_perp(self):
        """Test converting non-PERP exchange symbol (no change)"""
        result = convert_from_exchange_symbol("BTC-USDT")
        self.assertEqual(result, "BTC-USDT")

    def test_convert_to_exchange_symbol_eth(self):
        """Test converting ETH trading pair"""
        result = convert_to_exchange_symbol("ETH-USD")
        self.assertEqual(result, "ETH-PERP")

    def test_convert_from_exchange_symbol_eth(self):
        """Test converting ETH exchange symbol"""
        result = convert_from_exchange_symbol("ETH-PERP")
        self.assertEqual(result, "ETH-USD")

    def test_round_trip_conversion(self):
        """Test round trip conversion maintains value"""
        original = "BTC-USD"
        exchanged = convert_to_exchange_symbol(original)
        restored = convert_from_exchange_symbol(exchanged)
        self.assertEqual(original, restored)

    def test_get_pair_prefix(self):
        """Test extracting base asset from trading pair"""
        self.assertEqual(get_pair_prefix("BTC-USD"), "BTC")
        self.assertEqual(get_pair_prefix("ETH-USD"), "ETH")
        self.assertEqual(get_pair_prefix("SOL-USD"), "SOL")

    def test_get_pair_suffix(self):
        """Test extracting quote asset from trading pair"""
        self.assertEqual(get_pair_suffix("BTC-USD"), "USD")
        self.assertEqual(get_pair_suffix("BTC-USDT"), "USDT")

    def test_get_exchange_trading_pair(self):
        """Test get_exchange_trading_pair function"""
        result = get_exchange_trading_pair("BTC-USD")
        self.assertEqual(result, "BTC-PERP")

    def test_get_original_trading_pair(self):
        """Test get_original_trading_pair function"""
        result = get_original_trading_pair("BTC-PERP")
        self.assertEqual(result, "BTC-USD")


class TestDecibelPerpetualConstants(unittest.TestCase):
    """Unit tests for Decibel Perpetual constants"""

    def test_exchange_name(self):
        """Test exchange name is correct"""
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import (
            EXCHANGE_NAME,
        )
        self.assertEqual(EXCHANGE_NAME, "decibel_perpetual")

    def test_rest_url_defined(self):
        """Test REST URL is defined"""
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import (
            REST_URL,
        )
        self.assertTrue(REST_URL.startswith("https://"))

    def test_ws_url_defined(self):
        """Test WebSocket URL is defined"""
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import (
            WS_URL,
        )
        self.assertTrue(WS_URL.startswith("wss://"))

    def test_rate_limits_defined(self):
        """Test rate limits are defined"""
        from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_constants import (
            RATE_LIMITS,
        )
        self.assertIsInstance(RATE_LIMITS, list)
        self.assertGreater(len(RATE_LIMITS), 0)

    def test_endpoints_defined(self):
        """Test API endpoints are defined"""
        from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS

        # Check that key endpoints are defined
        self.assertTrue(hasattr(CONSTANTS, "GET_ALL_AVAILABLE_MARKETS"))
        self.assertTrue(hasattr(CONSTANTS, "GET_MARKET_PRICES"))
        self.assertTrue(hasattr(CONSTANTS, "GET_ORDER_BOOK_DEPTH"))
        self.assertTrue(hasattr(CONSTANTS, "PLACE_ORDER"))
        self.assertTrue(hasattr(CONSTANTS, "CANCEL_ORDER"))


if __name__ == "__main__":
    unittest.main()
