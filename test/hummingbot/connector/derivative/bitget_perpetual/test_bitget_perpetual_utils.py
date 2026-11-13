from unittest import TestCase

from hummingbot.connector.derivative.bitget_perpetual import (
    bitget_perpetual_constants as CONSTANTS,
    bitget_perpetual_utils as utils,
)


class BitgetPerpetualUtilsTests(TestCase):

    def test_is_exchange_information_valid(self):
        self.assertTrue(utils.is_exchange_information_valid({"symbol": "BTCUSDT"}))
        self.assertTrue(utils.is_exchange_information_valid({"symbol": "BTCUSDT", "deliveryPeriod": ""}))
        self.assertFalse(utils.is_exchange_information_valid({"symbol": ""}))
        self.assertFalse(utils.is_exchange_information_valid({}))

    def test_is_exchange_information_valid_excludes_dated_futures(self):
        self.assertFalse(
            utils.is_exchange_information_valid({"symbol": "BTCUSDT0327", "deliveryPeriod": "this_quarter"})
        )

    def test_is_instrument_tradable_requires_an_online_listing(self):
        self.assertTrue(utils.is_instrument_tradable({"symbol": "BTCUSDT", "status": "online"}))
        self.assertFalse(utils.is_instrument_tradable({"symbol": "BTCUSDT", "status": "offline"}))
        self.assertFalse(utils.is_instrument_tradable({"symbol": "BTCUSDT"}))
        self.assertFalse(utils.is_instrument_tradable({"status": "online"}))

    def test_is_instrument_tradable_excludes_dated_futures(self):
        self.assertFalse(
            utils.is_instrument_tradable(
                {"symbol": "BTCUSDT0327", "status": "online", "deliveryPeriod": "this_quarter"}
            )
        )

    def test_default_fees_deduct_buy_fees_from_returns(self):
        self.assertTrue(utils.DEFAULT_FEES.buy_percent_fee_deducted_from_returns)

    def test_config_map_connector_name(self):
        self.assertEqual(CONSTANTS.EXCHANGE_NAME, utils.KEYS.connector)
