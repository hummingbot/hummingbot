from unittest import TestCase

import pandas as pd

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_utils as utils


class BybitPerpetualUtilsTests(TestCase):
    def test_is_exchange_information_valid(self):
        exchange_info = {
            "name": "BTCUSD",
            "alias": "BTCUSD",
            "status": "Trading",
            "base_currency": "BTC",
            "quote_currency": "USD",
            "price_scale": 2,
            "taker_fee": "0.00075",
            "maker_fee": "-0.00025",
            "funding_interval": 480,
            "leverage_filter": {
                "min_leverage": 1,
                "max_leverage": 100,
                "leverage_step": "0.01"
            },
            "price_filter": {
                "min_price": "0.5",
                "max_price": "999999.5",
                "tick_size": "0.5"
            },
            "lot_size_filter": {
                "max_trading_qty": 1000000,
                "min_trading_qty": 1,
                "qty_step": 1,
                "post_only_max_trading_qty": "5000000"
            }
        }

        self.assertTrue(utils.is_exchange_information_valid(exchange_info))

        exchange_info["status"] = "Closed"

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

        del exchange_info["status"]

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

    def test_get_linear_non_linear_split(self):
        trading_pairs = ["ETH-USDT", "ETH-BTC"]
        linear_trading_pairs, non_linear_trading_pairs = utils.get_linear_non_linear_split(trading_pairs)

        self.assertEqual(["ETH-USDT"], linear_trading_pairs)
        self.assertEqual(["ETH-BTC"], non_linear_trading_pairs)

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
