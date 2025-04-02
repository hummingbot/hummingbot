from decimal import Decimal
from unittest import TestCase

from pydantic import SecretStr

from hummingbot.connector.exchange.bitstamp.bitstamp_utils import DEFAULT_FEES, BitstampConfigMap


class BitstampUtilsTests(TestCase):

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
        self.assertEqual(DEFAULT_FEES.maker_percent_fee_decimal, Decimal("0.1"))
        self.assertEqual(DEFAULT_FEES.taker_percent_fee_decimal, Decimal("0.2"))

    def test_bitstamp_config_map(self):
        config_map = BitstampConfigMap(
            bitstamp_api_key="test_key",
            bitstamp_api_secret="test_secret"
        )
        self.assertEqual(config_map.connector, "bitstamp")
        self.assertEqual(config_map.bitstamp_api_key, SecretStr("test_key"))
        self.assertEqual(config_map.bitstamp_api_secret, SecretStr("test_secret"))
