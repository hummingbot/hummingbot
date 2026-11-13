from unittest import TestCase

from hummingbot.connector.exchange.bitget import bitget_constants as CONSTANTS, bitget_utils as utils


class BitgetUtilsTests(TestCase):

    def test_is_exchange_information_valid(self):
        self.assertTrue(utils.is_exchange_information_valid({"symbol": "BTCUSDT"}))
        self.assertFalse(utils.is_exchange_information_valid({"symbol": ""}))
        self.assertFalse(utils.is_exchange_information_valid({}))

    def test_is_exchange_information_valid_keeps_suspended_pairs_resolvable(self):
        self.assertTrue(utils.is_exchange_information_valid({"symbol": "BTCUSDT", "status": "offline"}))

    def test_is_instrument_tradable_requires_an_online_listing(self):
        self.assertTrue(utils.is_instrument_tradable({"symbol": "BTCUSDT", "status": "online"}))
        self.assertFalse(utils.is_instrument_tradable({"symbol": "BTCUSDT", "status": "offline"}))
        self.assertFalse(utils.is_instrument_tradable({"symbol": "BTCUSDT"}))
        self.assertFalse(utils.is_instrument_tradable({"status": "online"}))

    def test_default_fees_deduct_buy_fees_from_returns(self):
        self.assertTrue(utils.DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_config_map_connector_name(self):
        self.assertEqual(CONSTANTS.EXCHANGE_NAME, utils.KEYS.connector)
