import unittest

from hummingbot.connector.exchange.kraken import kraken_utils as utils


class KrakenUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "XBT"
        cls.hb_base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.hb_base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.hb_base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.ex_ws_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"

    def test_convert_from_exchange_symbol(self):
        self.assertEqual(self.hb_base_asset, utils.convert_from_exchange_symbol(self.base_asset))
        self.assertEqual(self.quote_asset, utils.convert_from_exchange_symbol(self.quote_asset))

    def test_convert_to_exchange_symbol(self):
        self.assertEqual(self.base_asset, utils.convert_to_exchange_symbol(self.hb_base_asset))
        self.assertEqual(self.quote_asset, utils.convert_to_exchange_symbol(self.quote_asset))

    def test_convert_to_exchange_trading_pair(self):
        self.assertEqual(self.ex_trading_pair, utils.convert_to_exchange_trading_pair(self.hb_trading_pair))
        self.assertEqual(self.ex_trading_pair, utils.convert_to_exchange_trading_pair(self.ex_ws_trading_pair))
        self.assertEqual(self.ex_trading_pair, utils.convert_to_exchange_trading_pair(self.ex_trading_pair))

    def test_split_to_base_quote(self):
        self.assertEqual((self.hb_base_asset, self.quote_asset), utils.split_to_base_quote(self.trading_pair))

    def test_convert_from_exchange_trading_pair(self):
        self.assertEqual(self.trading_pair, utils.convert_from_exchange_trading_pair(self.trading_pair))
        self.assertEqual(self.trading_pair,
                         utils.convert_from_exchange_trading_pair(self.ex_trading_pair, ("BTC-USDT", "ETH-USDT")))
        self.assertEqual(self.trading_pair, utils.convert_from_exchange_trading_pair(self.ex_ws_trading_pair))

    def test_build_rate_limits_by_tier(self):
        self.assertIsNotNone(utils.build_rate_limits_by_tier())
