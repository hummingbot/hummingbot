from unittest import TestCase

from hummingbot.connector.derivative.hashkey_perpetual import hashkey_perpetual_utils as utils


class HashkeyPerpetualUtilsTests(TestCase):
    def test_is_exchange_information_valid(self):
        exchange_info = {
            "symbol": "ETHUSDT-PERPETUAL",
            "symbolName": "ETHUSDT-PERPETUAL",
            "status": "TRADING",
            "baseAsset": "ETHUSDT-PERPETUAL",
            "baseAssetName": "ETHUSDT-PERPETUAL",
            "baseAssetPrecision": "0.001",
            "quoteAsset": "USDT",
            "quoteAssetName": "USDT",
            "quotePrecision": "0.00000001",
            "retailAllowed": False,
            "piAllowed": False,
            "corporateAllowed": False,
            "omnibusAllowed": False,
            "icebergAllowed": False,
            "isAggregate": False,
            "allowMargin": False,
            "filters": [
                {
                    "minPrice": "0.01",
                    "maxPrice": "100000.00000000",
                    "tickSize": "0.01",
                    "filterType": "PRICE_FILTER"
                },
                {
                    "minQty": "0.001",
                    "maxQty": "50",
                    "stepSize": "0.001",
                    "marketOrderMinQty": "0",
                    "marketOrderMaxQty": "0",
                    "filterType": "LOT_SIZE"
                },
                {
                    "minNotional": "0",
                    "filterType": "MIN_NOTIONAL"
                },
                {
                    "maxSellPrice": "99999",
                    "buyPriceUpRate": "0.05",
                    "sellPriceDownRate": "0.05",
                    "maxEntrustNum": 200,
                    "maxConditionNum": 200,
                    "filterType": "LIMIT_TRADING"
                },
                {
                    "buyPriceUpRate": "0.05",
                    "sellPriceDownRate": "0.05",
                    "filterType": "MARKET_TRADING"
                },
                {
                    "noAllowMarketStartTime": "0",
                    "noAllowMarketEndTime": "0",
                    "limitOrderStartTime": "0",
                    "limitOrderEndTime": "0",
                    "limitMinPrice": "0",
                    "limitMaxPrice": "0",
                    "filterType": "OPEN_QUOTE"
                }
            ]
        }

        self.assertTrue(utils.is_exchange_information_valid(exchange_info))

        exchange_info["status"] = "Closed"

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

        del exchange_info["status"]

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

    def test_is_linear_perpetual(self):
        self.assertTrue(utils.is_linear_perpetual("BTC-USDT"))
        self.assertFalse(utils.is_linear_perpetual("BTC-USD"))

    def test_get_next_funding_timestamp(self):
        current_timestamp = 1626192000.0
        self.assertEqual(utils.get_next_funding_timestamp(current_timestamp), 1626220800.0)
