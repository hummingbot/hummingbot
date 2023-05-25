import unittest
from decimal import Decimal

from hummingbot.connector.exchange.coinbase_advanced_trade.cat_utils import (
    DEFAULT_FEES,
    AccountInfo,
    ProductInfo,
    is_product_tradable,
    is_valid_account,
)


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

    def test_is_product_tradable(self):
        valid_product: ProductInfo = {
            "product_type": "SPOT",
            "trading_disabled": False,
            "is_disabled": False,
            "cancel_only": False,
            "limit_only": False,
            "post_only": False,
            "auction_mode": False
        }
        self.assertTrue(is_product_tradable(valid_product))

        invalid_product: ProductInfo = {
            "product_type": "SPOT",
            "trading_disabled": True,  # Change this to True
            "is_disabled": False,
            "cancel_only": False,
            "limit_only": False,
            "post_only": False,
            "auction_mode": False
        }
        self.assertFalse(is_product_tradable(invalid_product))

    def test_is_valid_account(self):
        valid_account: AccountInfo = {
            "active": True,
            "type": "ACCOUNT_TYPE_CRYPTO",
            "ready": True,
            # Other fields are omitted for simplicity
        }
        self.assertTrue(is_valid_account(valid_account))

        invalid_account: AccountInfo = {
            "active": False,  # Change this to False
            "type": "ACCOUNT_TYPE_CRYPTO",
            "ready": True,
            # Other fields are omitted for simplicity
        }
        self.assertFalse(is_valid_account(invalid_account))
