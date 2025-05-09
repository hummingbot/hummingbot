import unittest

import hummingbot.connector.derivative.kucoin_perpetual.kucoin_perpetual_utils as utils


class TradingPairUtilsTest(unittest.TestCase):
    def test_is_exchange_information_valid(self):
        exchange_info = {
            "symbol": "XBTUSDTM",
            "rootSymbol": "USDT",
            "type": "FFWCSX",
            "firstOpenDate": 1585555200000,
            "expireDate": None,
            "settleDate": None,
            "baseCurrency": "XBT",
            "quoteCurrency": "USDT",
            "settleCurrency": "USDT",
            "maxOrderQty": 1000000,
            "maxPrice": 1000000.0,
            "lotSize": 1,
            "tickSize": 1.0,
            "indexPriceTickSize": 0.01,
            "multiplier": 0.001,
            "initialMargin": 0.01,
            "maintainMargin": 0.005,
            "maxRiskLimit": 2000000,
            "minRiskLimit": 2000000,
            "riskStep": 1000000,
            "makerFeeRate": 0.0002,
            "takerFeeRate": 0.0006,
            "takerFixFee": 0.0,
            "makerFixFee": 0.0,
            "settlementFee": None,
            "isDeleverage": True,
            "isQuanto": True,
            "isInverse": False,
            "markMethod": "FairPrice",
            "fairMethod": "FundingRate",
            "fundingBaseSymbol": ".XBTINT8H",
            "fundingQuoteSymbol": ".USDTINT8H",
            "fundingRateSymbol": ".XBTUSDTMFPI8H",
            "indexSymbol": ".KXBTUSDT",
            "settlementSymbol": "",
            "status": "Open",
            "fundingFeeRate": 0.0001,
            "predictedFundingFeeRate": 0.0001,
            "openInterest": "5191275",
            "turnoverOf24h": 2361994501.712677,
            "volumeOf24h": 56067.116,
            "markPrice": 44514.03,
            "indexPrice": 44510.78,
            "lastTradePrice": 44493.0,
            "nextFundingRateTime": 21031525,
            "maxLeverage": 100,
            "sourceExchanges": [
                "htx",
                "Okex",
                "Binance",
                "Kucoin",
                "Poloniex",
            ],
            "premiumsSymbol1M": ".XBTUSDTMPI",
            "premiumsSymbol8H": ".XBTUSDTMPI8H",
            "fundingBaseSymbol1M": ".XBTINT",
            "fundingQuoteSymbol1M": ".USDTINT",
            "lowPrice": 38040,
            "highPrice": 44948,
            "priceChgPct": 0.1702,
            "priceChg": 6476
        }

        self.assertTrue(utils.is_exchange_information_valid(exchange_info))

        exchange_info["status"] = "Closed"

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))

        del exchange_info["status"]

        self.assertFalse(utils.is_exchange_information_valid(exchange_info))


if __name__ == '__main__':
    unittest.main()
