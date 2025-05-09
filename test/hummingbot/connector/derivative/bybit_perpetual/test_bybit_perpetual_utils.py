from unittest import TestCase

from hummingbot.connector.derivative.bybit_perpetual import bybit_perpetual_utils as utils


class BybitPerpetualUtilsTests(TestCase):
    def test_is_exchange_information_valid(self):
        exchange_info = {
            "symbol": "BTCUSDT",
            "contractType": "LinearPerpetual",
            "status": "Trading",
            "baseCoin": "BTC",
            "quoteCoin": "USDT",
            "launchTime": "1585526400000",
            "deliveryTime": "0",
            "deliveryFeeRate": "",
            "priceScale": "2",
            "leverageFilter": {
                "minLeverage": "1",
                "maxLeverage": "100.00",
                "leverageStep": "0.01"
            },
            "priceFilter": {
                "minPrice": "0.10",
                "maxPrice": "199999.80",
                "tickSize": "0.10"
            },
            "lotSizeFilter": {
                "maxOrderQty": "100.000",
                "maxMktOrderQty": "100.000",
                "minOrderQty": "0.001",
                "qtyStep": "0.001",
                "postOnlyMaxOrderQty": "1000.000",
                "minNotionalValue": "5"
            },
            "unifiedMarginTrade": True,
            "fundingInterval": 480,
            "settleCoin": "USDT",
            "copyTrading": "both",
            "upperFundingRate": "0.00375",
            "lowerFundingRate": "-0.00375"
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
        # 2024-08-30-01:00:00 UTC
        timestamp = 1724979600
        # 2024-08-30-08:00:00 UTC
        expected_ts = 1725004800
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # 2024-08-30-09:00:00 UTC
        timestamp = 1725008400
        # 2024-08-30-16:00:00 UTC
        expected_ts = 1725033600
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))

        # 2024-08-30-17:00:00 UTC
        timestamp = 1725037200
        # 2024-08-31-00:00:00 UTC
        expected_ts = 1725062400
        self.assertEqual(expected_ts, utils.get_next_funding_timestamp(timestamp))
