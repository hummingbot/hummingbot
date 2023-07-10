import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utils import DEFAULT_FEES


class CoinbaseAdvancedTradeUtilTestCases(unittest.TestCase):

    quote_asset = None
    base_asset = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.hb_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def test_default_fees(self):
        self.assertEqual(DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.004"))
        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.006"))
        self.assertFalse(DEFAULT_FEES.buy_percent_fee_deducted_from_returns)
