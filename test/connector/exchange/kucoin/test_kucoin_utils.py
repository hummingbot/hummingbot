import unittest

from hummingbot.connector.exchange.kucoin.kucoin_utils import (
    ASSET_TO_NAME_MAPPING,
    NAME_TO_ASSET_MAPPING,
    split_trading_pair,
    convert_asset_from_exchange,
    convert_asset_to_exchange,
    convert_from_exchange_trading_pair,
    convert_to_exchange_trading_pair,
)


class KucoinUtilsUnitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def test_split_trading_pair(self):
        # Test (1) Non-matching trading pair
        expected_output = self.base_asset, self.quote_asset
        self.assertEqual(expected_output, split_trading_pair(self.trading_pair))

        # Test (2) Matching base asset
        matching_asset, asset_name = next(iter(ASSET_TO_NAME_MAPPING.items()))

        trading_pair = f"{matching_asset}-{self.quote_asset}"
        expected_output = asset_name, self.quote_asset

        self.assertEqual(expected_output, split_trading_pair(trading_pair))

        # Test (3) Matching quote asset
        matching_asset, asset_name = next(iter(ASSET_TO_NAME_MAPPING.items()))

        trading_pair = f"{self.base_asset}-{matching_asset}"
        expected_output = self.base_asset, asset_name

        self.assertEqual(expected_output, split_trading_pair(trading_pair))

    def test_convert_asset_from_exchange(self):
        # Test (1) Regular asset
        self.assertEqual(self.base_asset, convert_asset_from_exchange(self.base_asset))

        # Test (2) Matching asset
        matching_asset, asset_name = next(iter(ASSET_TO_NAME_MAPPING.items()))

        self.assertEqual(asset_name, convert_asset_from_exchange(matching_asset))

    def test_convert_asset_to_exchange(self):
        # Test (1) Regular asset
        self.assertEqual(self.base_asset, convert_asset_to_exchange(self.base_asset))

        # Test (2) Matching asset
        asset_name, matching_asset = next(iter(NAME_TO_ASSET_MAPPING.items()))

        self.assertEqual(matching_asset, convert_asset_to_exchange(asset_name))

    def test_convert_from_exchange_trading_pair(self):
        # Test (1) Non-matching trading pair
        self.assertEqual(self.trading_pair, convert_from_exchange_trading_pair(self.trading_pair))

        # Test (2) Matching base asset
        matching_asset, asset_name = next(iter(ASSET_TO_NAME_MAPPING.items()))

        trading_pair = f"{matching_asset}-{self.quote_asset}"
        expected_trading_pair = f"{asset_name}-{self.quote_asset}"

        self.assertEqual(expected_trading_pair, convert_from_exchange_trading_pair(trading_pair))

        # Test (3) Matching quote asset
        matching_asset, asset_name = next(iter(ASSET_TO_NAME_MAPPING.items()))

        trading_pair = f"{self.base_asset}-{matching_asset}"
        expected_trading_pair = f"{self.base_asset}-{asset_name}"

        self.assertEqual(expected_trading_pair, convert_from_exchange_trading_pair(trading_pair))

    def test_convert_to_exchange_trading_pair(self):
        # Test (1) Regular asset
        self.assertEqual(self.trading_pair, convert_to_exchange_trading_pair(self.trading_pair))

        # Test (2) Matching asset
        matching_asset, asset_name = next(iter(NAME_TO_ASSET_MAPPING.items()))

        trading_pair = f"{matching_asset}-{self.quote_asset}"
        expected_trading_pair = f"{asset_name}-{self.quote_asset}"

        self.assertEqual(expected_trading_pair, convert_to_exchange_trading_pair(trading_pair))
