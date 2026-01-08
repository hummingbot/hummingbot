from unittest import TestCase

from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.evedex_perpetual import evedex_perpetual_web_utils as web_utils


class EvedexPerpetualWebUtilsTests(TestCase):
    def test_rest_url_mainnet(self):
        """Test REST URL generation for mainnet."""
        url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_URL, domain="evedex_perpetual")
        expected = f"{CONSTANTS.PERPETUAL_BASE_URL}{CONSTANTS.EXCHANGE_INFO_URL}"
        self.assertEqual(url, expected)

    def test_rest_url_testnet(self):
        """Test REST URL generation for testnet."""
        url = web_utils.rest_url(CONSTANTS.EXCHANGE_INFO_URL, domain="evedex_perpetual_testnet")
        expected = f"{CONSTANTS.TESTNET_BASE_URL}{CONSTANTS.EXCHANGE_INFO_URL}"
        self.assertEqual(url, expected)

    def test_wss_url_mainnet(self):
        """Test WebSocket URL for mainnet."""
        url = web_utils.wss_url(domain="evedex_perpetual")
        self.assertEqual(url, CONSTANTS.PERPETUAL_WS_URL)

    def test_wss_url_testnet(self):
        """Test WebSocket URL for testnet."""
        url = web_utils.wss_url(domain="evedex_perpetual_testnet")
        self.assertEqual(url, CONSTANTS.TESTNET_WS_URL)

    def test_public_rest_url(self):
        """Test public REST URL generation."""
        url = web_utils.public_rest_url(CONSTANTS.MARKET_DEPTH_URL)
        expected = f"{CONSTANTS.PERPETUAL_BASE_URL}{CONSTANTS.MARKET_DEPTH_URL}"
        self.assertEqual(url, expected)

    def test_private_rest_url(self):
        """Test private REST URL generation."""
        url = web_utils.private_rest_url(CONSTANTS.CREATE_ORDER_URL)
        expected = f"{CONSTANTS.PERPETUAL_BASE_URL}{CONSTANTS.CREATE_ORDER_URL}"
        self.assertEqual(url, expected)

    def test_convert_to_exchange_trading_pair(self):
        """Test Hummingbot to exchange trading pair conversion."""
        result = web_utils.convert_to_exchange_trading_pair("BTC-USDT")
        self.assertEqual(result, "BTCUSDT")

    def test_convert_from_exchange_trading_pair_usdt(self):
        """Test exchange to Hummingbot trading pair conversion with USDT."""
        result = web_utils.convert_from_exchange_trading_pair("BTCUSDT")
        self.assertEqual(result, "BTC-USDT")

    def test_convert_from_exchange_trading_pair_usdc(self):
        """Test exchange to Hummingbot trading pair conversion with USDC."""
        result = web_utils.convert_from_exchange_trading_pair("ETHUSDC")
        self.assertEqual(result, "ETH-USDC")

    def test_convert_from_exchange_trading_pair_usd(self):
        """Test exchange to Hummingbot trading pair conversion with USD."""
        result = web_utils.convert_from_exchange_trading_pair("BTCUSD")
        self.assertEqual(result, "BTC-USD")

    def test_is_exchange_information_valid_active(self):
        """Test that active instruments are valid."""
        rule = {"status": "active"}
        self.assertTrue(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_trading(self):
        """Test that trading instruments are valid."""
        rule = {"status": "trading"}
        self.assertTrue(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_inactive(self):
        """Test that inactive instruments are invalid."""
        rule = {"status": "inactive"}
        self.assertFalse(web_utils.is_exchange_information_valid(rule))

    def test_is_exchange_information_valid_halted(self):
        """Test that halted instruments are invalid."""
        rule = {"status": "halted"}
        self.assertFalse(web_utils.is_exchange_information_valid(rule))

    def test_float_to_string(self):
        """Test float to string conversion."""
        result = web_utils.float_to_string(123.45000000)
        self.assertEqual(result, "123.45")

    def test_float_to_string_integer(self):
        """Test integer float to string conversion."""
        result = web_utils.float_to_string(100.0)
        self.assertEqual(result, "100")

    def test_float_to_string_precision(self):
        """Test float to string with high precision."""
        result = web_utils.float_to_string(0.00001234, precision=8)
        self.assertEqual(result, "0.00001234")

    def test_parse_order_side(self):
        """Test order side parsing."""
        self.assertEqual(web_utils.parse_order_side("BUY"), "buy")
        self.assertEqual(web_utils.parse_order_side("SELL"), "sell")

    def test_parse_order_type(self):
        """Test order type parsing."""
        self.assertEqual(web_utils.parse_order_type("LIMIT"), "limit")
        self.assertEqual(web_utils.parse_order_type("MARKET"), "market")

    def test_create_throttler(self):
        """Test throttler creation."""
        throttler = web_utils.create_throttler()
        self.assertIsNotNone(throttler)
