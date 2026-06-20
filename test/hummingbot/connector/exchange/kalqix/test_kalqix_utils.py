import unittest
from decimal import Decimal

from hummingbot.connector.exchange.kalqix import kalqix_utils as utils


class KalqixUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_ticker_path = f"{cls.base_asset}_{cls.quote_asset}"   # URL form
        cls.exchange_ticker_body = f"{cls.base_asset}/{cls.quote_asset}"   # body form

    def test_is_exchange_information_valid(self):
        self.assertTrue(utils.is_exchange_information_valid({"status": "ACTIVE"}))
        self.assertFalse(utils.is_exchange_information_valid({"status": "PAUSED"}))
        self.assertFalse(utils.is_exchange_information_valid({"status": "DELISTED"}))
        self.assertFalse(utils.is_exchange_information_valid({}))

    def test_convert_to_exchange_ticker_path(self):
        self.assertEqual(self.exchange_ticker_path, utils.convert_to_exchange_ticker_path(self.trading_pair))

    def test_convert_to_exchange_ticker_body(self):
        self.assertEqual(self.exchange_ticker_body, utils.convert_to_exchange_ticker_body(self.trading_pair))

    def test_convert_from_exchange_trading_pair_handles_both_conventions(self):
        self.assertEqual(self.trading_pair, utils.convert_from_exchange_trading_pair(self.exchange_ticker_body))
        self.assertEqual(self.trading_pair, utils.convert_from_exchange_trading_pair(self.exchange_ticker_path))

    def test_default_fees_present(self):
        self.assertEqual(Decimal("0.001"), utils.DEFAULT_FEES.maker_percent_fee_decimal)
        self.assertEqual(Decimal("0.001"), utils.DEFAULT_FEES.taker_percent_fee_decimal)
        self.assertTrue(utils.DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_keys_config_map(self):
        self.assertEqual("kalqix", utils.KEYS.connector)

    def test_other_domains_registration(self):
        self.assertEqual(["kalqix_testnet"], utils.OTHER_DOMAINS)
        self.assertEqual({"kalqix_testnet": "testnet"}, utils.OTHER_DOMAINS_PARAMETER)
        self.assertIn("kalqix_testnet", utils.OTHER_DOMAINS_DEFAULT_FEES)
        self.assertIn("kalqix_testnet", utils.OTHER_DOMAINS_KEYS)
        self.assertEqual("kalqix_testnet", utils.OTHER_DOMAINS_KEYS["kalqix_testnet"].connector)


if __name__ == "__main__":
    unittest.main()
