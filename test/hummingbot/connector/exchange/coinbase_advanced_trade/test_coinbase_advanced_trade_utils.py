import unittest
from decimal import Decimal

from pydantic import SecretStr

import hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_constants as CONSTANTS
from hummingbot.connector.exchange.coinbase_advanced_trade.coinbase_advanced_trade_utils import (
    DEFAULT_FEES,
    CoinbaseAdvancedTradeConfigMap,
    CoinbaseAdvancedTradeRESTRequest,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


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

    def test_coinbase_advanced_trade_rest_request(self):
        # Test without authentication
        req = CoinbaseAdvancedTradeRESTRequest(is_auth_required=False, method=RESTMethod.GET, endpoint="/test")
        self.assertEqual(req.base_url, CONSTANTS.REST_URL)

        # Test with authentication but without endpoint
        with self.assertRaises(ValueError):
            CoinbaseAdvancedTradeRESTRequest(is_auth_required=True, method=RESTMethod.GET)

        # Test with authentication and endpoint
        req = CoinbaseAdvancedTradeRESTRequest(is_auth_required=True, endpoint="/test", method=RESTMethod.GET)
        self.assertEqual(req.base_url, CONSTANTS.REST_URL)

    def test_coinbase_advanced_trade_config_map(self):
        config_map = CoinbaseAdvancedTradeConfigMap(
            coinbase_advanced_trade_api_key="test_key",
            coinbase_advanced_trade_api_secret="test_secret"
        )
        self.assertEqual(config_map.connector, "coinbase_advanced_trade")
        self.assertEqual(config_map.coinbase_advanced_trade_api_key, SecretStr("test_key"))
        self.assertEqual(config_map.coinbase_advanced_trade_api_secret, SecretStr("test_secret"))
