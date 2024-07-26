import unittest
from datetime import datetime
from decimal import Decimal

from hummingbot.connector.exchange.tegro import tegro_utils as utils


class TegroeUtilTestCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def test_datetime_val_or_now(self):
        self.assertIsNone(utils.datetime_val_or_now('NotValidDate', '', False))
        self.assertLessEqual(datetime.now(), utils.datetime_val_or_now('NotValidDate', '', True))
        self.assertLessEqual(datetime.now(), utils.datetime_val_or_now('NotValidDate', ''))
        _now = '2023-04-19T18:53:17.981Z'
        _fNow = datetime.strptime(_now, '%Y-%m-%dT%H:%M:%S.%fZ')
        self.assertEqual(_fNow, utils.datetime_val_or_now(_now))

    def test_decimal_val_or_none(self):
        self.assertIsNone(utils.decimal_val_or_none('NotValidDecimal'))
        self.assertIsNone(utils.decimal_val_or_none('NotValidDecimal', True))
        self.assertEqual(0, utils.decimal_val_or_none('NotValidDecimal', False))
        _dec = '2023.0419'
        self.assertEqual(Decimal(_dec), utils.decimal_val_or_none(_dec))

    def test_int_val_or_none(self):
        self.assertIsNone(utils.int_val_or_none('NotValidInt'))
        self.assertIsNone(utils.int_val_or_none('NotValidInt', True))
        self.assertEqual(0, utils.int_val_or_none('NotValidInt', False))
        _dec = '2023'
        self.assertEqual(2023, utils.int_val_or_none(_dec))

    def test_is_exchange_information_valid(self):
        valid_info = {
            "state": "verified",
            "symbol": "COINALPHA_HBOT"
        }
        self.assertTrue(utils.is_exchange_information_valid(valid_info))
