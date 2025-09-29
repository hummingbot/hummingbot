import unittest

import hummingbot.connector.exchange.coinmate.coinmate_constants as CONSTANTS
from hummingbot.connector.exchange.coinmate import coinmate_web_utils as web_utils


class CoinmateWebUtilTestCases(unittest.TestCase):

    def test_public_rest_url(self):
        path_url = "/ticker"
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.public_rest_url(path_url))

    def test_private_rest_url(self):
        path_url = "/balances"
        expected_url = CONSTANTS.REST_URL + path_url
        self.assertEqual(expected_url, web_utils.private_rest_url(path_url))

    def test_convert_to_exchange_trading_pair(self):
        """Test conversion from Hummingbot to Coinmate format"""
        result = web_utils.convert_to_exchange_trading_pair("BTC-EUR")
        self.assertEqual(result, "BTC_EUR")
        
        result = web_utils.convert_to_exchange_trading_pair("ETH-CZK")
        self.assertEqual(result, "ETH_CZK")
        
        # Test edge case - no dash
        result = web_utils.convert_to_exchange_trading_pair("BTCEUR")
        self.assertEqual(result, "BTCEUR")

    def test_convert_from_exchange_trading_pair(self):
        """Test conversion from Coinmate to Hummingbot format"""
        result = web_utils.convert_from_exchange_trading_pair("BTC_EUR")
        self.assertEqual(result, "BTC-EUR")
        
        result = web_utils.convert_from_exchange_trading_pair("ETH_CZK")
        self.assertEqual(result, "ETH-CZK")
        
        # Test edge case - no underscore
        result = web_utils.convert_from_exchange_trading_pair("BTCEUR")
        self.assertEqual(result, "BTCEUR")

    def test_bidirectional_symbol_conversion(self):
        """Test that symbol conversion is reversible"""
        original = "BTC-EUR"
        converted = web_utils.convert_to_exchange_trading_pair(original)
        back = web_utils.convert_from_exchange_trading_pair(converted)
        self.assertEqual(back, original)

    def test_get_exchange_base_quote_from_market_name(self):
        """Test base and quote currency extraction"""
        base, quote = web_utils.get_exchange_base_quote_from_market_name("BTC_EUR")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "EUR")
        
        base, quote = web_utils.get_exchange_base_quote_from_market_name("BTC-EUR")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "EUR")
        
        # Test fallback with known quote currencies
        base, quote = web_utils.get_exchange_base_quote_from_market_name("BTCEUR")
        self.assertEqual(base, "BTC")
        self.assertEqual(quote, "EUR")