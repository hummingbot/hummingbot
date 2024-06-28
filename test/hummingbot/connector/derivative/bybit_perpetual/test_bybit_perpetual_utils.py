from unittest import TestCase

import pandas as pd

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_utils as utils


class BybitPerpetualUtilsTests(TestCase):
    def test_is_exchange_information_valid(self):
        exchange_info = {
            "symbol": "BTCUSDT",
            "baseCoin": "BTC",
            "quoteCoin": "USDT",
            "innovation": "0",
            "status": "Trading",
            "marginTrading": "both",
            "lotSizeFilter": {
                "basePrecision": "0.000001",
                "quotePrecision": "0.00000001",
                "minOrderQty": "0.000048",
                "maxOrderQty": "71.73956243",
                "minOrderAmt": "1",
                "maxOrderAmt": "2000000"
            },
            "priceFilter": {
                "tickSize": "0.01"
            },
            "riskParameters": {
                "limitParameter": "0.05",
                "marketParameter": "0.05"
            }
        }

        self.assertTrue(utils.is_exchange_information_valid(exchange_info))

        exchange_info["status"] = "Closed"

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

        del exchange_info["status"]

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

    def test_get_linear_non_linear_split(self):
        trading_pairs = ["ETH-USDT", "ETH-BTC"]
        linear_trading_pairs, _ = utils.get_linear_non_linear_split(trading_pairs)

        self.assertEqual(["ETH-USDT"], linear_trading_pairs)

    def test_get_next_funding_timestamp(self):
        # Simulate 01:00 UTC
        timestamp = pd.Timestamp("2021-08-21-01:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-21-08:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # Simulate 09:00 UTC
        timestamp = pd.Timestamp("2021-08-21-09:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-21-16:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # Simulate 17:00 UTC
        timestamp = pd.Timestamp("2021-08-21-17:00:00", tz="UTC").timestamp()
        expected_ts = pd.Timestamp("2021-08-22-00:00:00", tz="UTC").timestamp()
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))
