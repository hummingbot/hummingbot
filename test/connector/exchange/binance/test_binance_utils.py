import unittest
import hummingbot.connector.exchange.binance.binance_utils as utils


class TradingPairUtilsTest(unittest.TestCase):
    def testParseThreeLettersBaseAndThreeLettersQuote(self):
        parsed_pair = utils.convert_from_exchange_trading_pair("BTCUSD")
        self.assertEqual(parsed_pair, "BTC-USD")

    def testParseThreeLettersBaseAndFourLettersQuote(self):
        parsed_pair = utils.convert_from_exchange_trading_pair("BTCUSDT")
        self.assertEqual(parsed_pair, "BTC-USDT")

    def testParseThreeLettersBaseAndThreeLettersfQuoteMatchingWithAFourLettersQuoteCandidate(self):
        parsed_pair = utils.convert_from_exchange_trading_pair("VETUSD")
        self.assertEqual(parsed_pair, "VET-USD")

    def testConvertToExchangeFormatThreeLettersBaseAndThreeLettersQuote(self):
        converted_pair = utils.convert_to_exchange_trading_pair("BTC-USD")
        self.assertEqual(converted_pair, "BTCUSD")

    def testConvertToExchangeFormatThreeLettersBaseAndFourLettersfQuote(self):
        converted_pair = utils.convert_to_exchange_trading_pair("BTC-USDT")
        self.assertEqual(converted_pair, "BTCUSDT")

    def testConvertToExchangeFormatThreeLettersBaseAndThreeLettersfQuoteMatchingWithAFourLettersQuoteCandidate(self):
        converted_pair = utils.convert_to_exchange_trading_pair("VET-USD")
        self.assertEqual(converted_pair, "VETUSD")


if __name__ == '__main__':
    unittest.main()
