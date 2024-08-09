import asyncio
import json
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.utils.tracking_nonce import get_tracking_nonce
from hummingbot.data_feed.candles_feed.kucoin_perpetual_candles import KucoinPerpetualCandles


class TestKucoinPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.kucoin_base_asset = "XBT"
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.kucoin_base_asset}-{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = KucoinPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.data_feed.symbols_dict = self.get_symbols_dict_mock()
        self.data_feed._ws_url = "wss://api.kucoin.com"
        self.data_feed._ws_token = "test"

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    @staticmethod
    def get_symbols_dict_mock():
        return {
            "XBT-USDT": "XBTUSDTM",
            "ETH-USDT": "ETHUSDTM",
            "SOL-USDT": "SOLUSDTM",
            "WIF-USDT": "WIFUSDTM"
        }

    @staticmethod
    def get_symbols_response_mock():
        return {
            "code": "200000",
            "data": [
                {
                    "symbol": "XBTUSDTM",
                    "rootSymbol": "USDT",
                    "type": "FFWCSX",
                    "firstOpenDate": 1585555200000,
                    "expireDate": "",
                    "settleDate": "",
                    "baseCurrency": "XBT",
                    "quoteCurrency": "USDT",
                    "settleCurrency": "USDT",
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000,
                    "lotSize": 1,
                    "tickSize": 0.1,
                    "indexPriceTickSize": 0.01,
                    "multiplier": 0.001,
                    "initialMargin": 0.008,
                    "maintainMargin": 0.004,
                    "maxRiskLimit": 100000,
                    "minRiskLimit": 100000,
                    "riskStep": 50000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0,
                    "makerFixFee": 0,
                    "settlementFee": "",
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
                    "fundingFeeRate": 0.000132,
                    "predictedFundingFeeRate": 0.000176,
                    "fundingRateGranularity": 28800000,
                    "openInterest": "8306597",
                    "turnoverOf24h": 560148040.312645,
                    "volumeOf24h": 8544.241,
                    "markPrice": 64681.31,
                    "indexPrice": 64681.1,
                    "lastTradePrice": 64679.9,
                    "nextFundingRateTime": 7466987,
                    "maxLeverage": 125,
                    "sourceExchanges": [
                        "okex",
                        "binance",
                        "kucoin",
                        "bybit",
                        "bitget",
                        "bitmart",
                        "gateio"
                    ],
                    "premiumsSymbol1M": ".XBTUSDTMPI",
                    "premiumsSymbol8H": ".XBTUSDTMPI8H",
                    "fundingBaseSymbol1M": ".XBTINT",
                    "fundingQuoteSymbol1M": ".USDTINT",
                    "lowPrice": 64278,
                    "highPrice": 67277.7,
                    "priceChgPct": -0.0245,
                    "priceChg": -1629.5
                },
                {
                    "symbol": "ETHUSDTM",
                    "rootSymbol": "USDT",
                    "type": "FFWCSX",
                    "firstOpenDate": 1591086000000,
                    "expireDate": "",
                    "settleDate": "",
                    "baseCurrency": "ETH",
                    "quoteCurrency": "USDT",
                    "settleCurrency": "USDT",
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000,
                    "lotSize": 1,
                    "tickSize": 0.01,
                    "indexPriceTickSize": 0.01,
                    "multiplier": 0.01,
                    "initialMargin": 0.01,
                    "maintainMargin": 0.005,
                    "maxRiskLimit": 100000,
                    "minRiskLimit": 100000,
                    "riskStep": 50000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0,
                    "makerFixFee": 0,
                    "settlementFee": "",
                    "isDeleverage": True,
                    "isQuanto": True,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "fundingBaseSymbol": ".ETHINT8H",
                    "fundingQuoteSymbol": ".USDTINT8H",
                    "fundingRateSymbol": ".ETHUSDTMFPI8H",
                    "indexSymbol": ".KETHUSDT",
                    "settlementSymbol": "",
                    "status": "Open",
                    "fundingFeeRate": 0.000094,
                    "predictedFundingFeeRate": 0.000074,
                    "fundingRateGranularity": 28800000,
                    "openInterest": "6506611",
                    "turnoverOf24h": 237761018.67718124,
                    "volumeOf24h": 69065.8,
                    "markPrice": 3409.13,
                    "indexPrice": 3409.11,
                    "lastTradePrice": 3409.38,
                    "nextFundingRateTime": 7466984,
                    "maxLeverage": 100,
                    "sourceExchanges": [
                        "okex",
                        "binance",
                        "kucoin",
                        "gateio",
                        "bybit",
                        "bitmart",
                        "bitget"
                    ],
                    "premiumsSymbol1M": ".ETHUSDTMPI",
                    "premiumsSymbol8H": ".ETHUSDTMPI8H",
                    "fundingBaseSymbol1M": ".ETHINT",
                    "fundingQuoteSymbol1M": ".USDTINT",
                    "lowPrice": 3350,
                    "highPrice": 3578.04,
                    "priceChgPct": -0.0371,
                    "priceChg": -131.59
                },
                {
                    "symbol": "SOLUSDTM",
                    "rootSymbol": "USDT",
                    "type": "FFWCSX",
                    "firstOpenDate": 1614153600000,
                    "expireDate": "",
                    "settleDate": "",
                    "baseCurrency": "SOL",
                    "quoteCurrency": "USDT",
                    "settleCurrency": "USDT",
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000,
                    "lotSize": 1,
                    "tickSize": 0.001,
                    "indexPriceTickSize": 0.001,
                    "multiplier": 0.1,
                    "initialMargin": 0.014,
                    "maintainMargin": 0.007,
                    "maxRiskLimit": 50000,
                    "minRiskLimit": 50000,
                    "riskStep": 25000,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0,
                    "makerFixFee": 0,
                    "settlementFee": "",
                    "isDeleverage": True,
                    "isQuanto": False,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "fundingBaseSymbol": ".SOLINT8H",
                    "fundingQuoteSymbol": ".USDTINT8H",
                    "fundingRateSymbol": ".SOLUSDTMFPI8H",
                    "indexSymbol": ".KSOLUSDT",
                    "settlementSymbol": "",
                    "status": "Open",
                    "fundingFeeRate": -0.000027,
                    "predictedFundingFeeRate": 0.000012,
                    "fundingRateGranularity": 28800000,
                    "openInterest": "7254789",
                    "turnoverOf24h": 194771311.87900543,
                    "volumeOf24h": 1422531.1,
                    "markPrice": 133.026,
                    "indexPrice": 133.031,
                    "lastTradePrice": 133.002,
                    "nextFundingRateTime": 7466981,
                    "maxLeverage": 75,
                    "sourceExchanges": [
                        "binance",
                        "okex",
                        "gateio",
                        "bybit",
                        "kucoin"
                    ],
                    "premiumsSymbol1M": ".SOLUSDTMPI",
                    "premiumsSymbol8H": ".SOLUSDTMPI8H",
                    "fundingBaseSymbol1M": ".SOLINT",
                    "fundingQuoteSymbol1M": ".USDTINT",
                    "lowPrice": 125.847,
                    "highPrice": 146.808,
                    "priceChgPct": -0.0783,
                    "priceChg": -11.303
                },
                {
                    "symbol": "WIFUSDTM",
                    "rootSymbol": "USDT",
                    "type": "FFWCSX",
                    "firstOpenDate": 1707292800000,
                    "expireDate": "",
                    "settleDate": "",
                    "baseCurrency": "WIF",
                    "quoteCurrency": "USDT",
                    "settleCurrency": "USDT",
                    "maxOrderQty": 1000000,
                    "maxPrice": 1000000,
                    "lotSize": 1,
                    "tickSize": 0.0001,
                    "indexPriceTickSize": 0.0001,
                    "multiplier": 10,
                    "initialMargin": 0.014,
                    "maintainMargin": 0.007,
                    "maxRiskLimit": 25000,
                    "minRiskLimit": 25000,
                    "riskStep": 12500,
                    "makerFeeRate": 0.0002,
                    "takerFeeRate": 0.0006,
                    "takerFixFee": 0,
                    "makerFixFee": 0,
                    "settlementFee": "",
                    "isDeleverage": True,
                    "isQuanto": False,
                    "isInverse": False,
                    "markMethod": "FairPrice",
                    "fairMethod": "FundingRate",
                    "fundingBaseSymbol": ".WIFINT8H",
                    "fundingQuoteSymbol": ".USDTINT8H",
                    "fundingRateSymbol": ".WIFUSDTMFPI8H",
                    "indexSymbol": ".KWIFUSDT",
                    "settlementSymbol": "",
                    "status": "Open",
                    "fundingFeeRate": 0.000131,
                    "predictedFundingFeeRate": 0.000045,
                    "fundingRateGranularity": 28800000,
                    "openInterest": "626433",
                    "turnoverOf24h": 55265460.63083267,
                    "volumeOf24h": 26115500,
                    "markPrice": 1.9407,
                    "indexPrice": 1.9405,
                    "lastTradePrice": 1.9405,
                    "nextFundingRateTime": 7466978,
                    "maxLeverage": 75,
                    "sourceExchanges": [
                        "gateio",
                        "bitmart",
                        "kucoin",
                        "mexc",
                        "bitget",
                        "binance"
                    ],
                    "premiumsSymbol1M": ".WIFUSDTMPI",
                    "premiumsSymbol8H": ".WIFUSDTMPI8H",
                    "fundingBaseSymbol1M": ".WIFINT",
                    "fundingQuoteSymbol1M": ".USDTINT",
                    "lowPrice": 1.9206,
                    "highPrice": 2.4554,
                    "priceChgPct": -0.1912,
                    "priceChg": -0.457
                }
            ]
        }

    def get_fetch_candles_data_mock(self):
        return [
            [1672981200, '16823.24000000', '16792.12000000', '16810.18000000', '16823.63000000', '6230.44034000', 0.0,
             0.0, 0.0, 0.0],
            [1672984800, '16809.74000000', '16779.96000000', '16786.86000000', '16816.45000000', '6529.22759000', 0.0,
             0.0, 0.0, 0.0],
            [1672988400, '16786.60000000', '16780.15000000', '16794.06000000', '16802.87000000', '5763.44917000', 0.0,
             0.0, 0.0, 0.0],
            [1672992000, '16794.33000000', '16791.47000000', '16802.11000000', '16812.22000000', '5475.13940000', 0.0,
             0.0, 0.0, 0.0],
        ]

    def get_candles_rest_data_mock(self):
        data = [
            [
                1672981200,
                "16823.24000000",
                "16823.63000000",
                "16792.12000000",
                "16810.18000000",
                "6230.44034000",
            ],
            [
                1672984800,
                "16809.74000000",
                "16816.45000000",
                "16779.96000000",
                "16786.86000000",
                "6529.22759000"
            ],
            [
                1672988400,
                "16786.60000000",
                "16802.87000000",
                "16780.15000000",
                "16794.06000000",
                "5763.44917000"
            ],
            [
                1672992000,
                "16794.33000000",
                "16812.22000000",
                "16791.47000000",
                "16802.11000000",
                "5475.13940000"
            ],
        ]
        return {"code": "200000", "data": data}

    def get_candles_ws_data_mock_1(self):
        data = {
            "type": "message",
            "topic": "/market/candles:XBT-USDT_1hour",
            "subject": "trade.candles.update",
            "data": {
                "symbol": "XBT-USDT",  # symbol
                "candles": [
                    "1589968800",  # Start time of the candle cycle
                    "9786.9",  # open price
                    "9740.8",  # close price
                    "9806.1",  # high price
                    "9732",  # low price
                    "27.45649579",  # Transaction volume
                    "268280.09830877"  # Transaction amount
                ],
                "time": 1589970010253893337  # now（us）
            }
        }
        return data

    def get_candles_ws_data_mock_2(self):
        data = {
            "type": "message",
            "topic": "/market/candles:XBT-USDT_1hour",
            "subject": "trade.candles.update",
            "data": {
                "symbol": "XBT-USDT",  # symbol
                "candles": [
                    "1589972400",  # Start time of the candle cycle
                    "9786.9",  # open price
                    "9740.8",  # close price
                    "9806.1",  # high price
                    "9732",  # low price
                    "27.45649579",  # Transaction volume
                    "268280.09830877"  # Transaction amount
                ],
                "time": 1589970010253893337  # now（us）
            }
        }
        return data

    @staticmethod
    def _success_subscription_mock():
        return {'id': str(get_tracking_nonce()),
                'privateChannel': False,
                'response': False,
                'topic': '/market/candles:XBT-USDT_1hour',
                'type': 'subscribe'}

    @staticmethod
    def get_public_token_response_mock():
        return {
            "code": "200000",
            "data": {
                "token": "2neAiuYvAU61ZDXANAGAsiL4-iAExhsBXZxftpOeh_55i3Ysy2q2LEsEWU64mdzUOPusi34M_wGoSf7iNyEWJ4aBZXpWhrmY9jKtqkdWoFa75w3istPvPtiYB9J6i9GjsxUuhPw3BlrzazF6ghq4L_u0MhKxG3x8TeN4aVbNiYo=.mvnekBb8DJegZIgYLs2FBQ==",
                "instanceServers": [
                    {
                        "endpoint": "wss://ws-api-spot.kucoin.com/",
                        "encrypt": True,
                        "protocol": "websocket",
                        "pingInterval": 18000,
                        "pingTimeout": 10000
                    }
                ]
            }
        }

    @aioresponses()
    def test_get_ws_token(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.public_ws_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_public_token_response_mock()
        mock_api.post(url=regex_url, body=json.dumps(data_mock))

        self.data_feed._ws_token = None
        self.data_feed._ws_url = None

        self.async_run_with_timeout(self.data_feed._get_ws_token(), timeout=5)

        self.assertEqual(self.data_feed._ws_token, data_mock["data"]["token"])
        self.assertEqual(self.data_feed._ws_url, data_mock["data"]["instanceServers"][0]["endpoint"])

    @aioresponses()
    def test_get_ws_token_raises_exception(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.public_ws_url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(url=regex_url, status=500)

        self.data_feed._ws_token = None
        self.data_feed._ws_url = None

        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_feed._get_ws_token(), timeout=5)

    @aioresponses()
    def test_get_symbols_dict(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.symbols_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_symbols_response_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        self.async_run_with_timeout(self.data_feed._get_symbols_dict(), timeout=5)

        self.assertEqual(self.data_feed.symbols_dict, self.get_symbols_dict_mock())

    @aioresponses()
    def test_get_symbols_dict_raises_exception(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.symbols_url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.get(url=regex_url, status=500)

        with self.assertRaises(Exception):
            self.async_run_with_timeout(self.data_feed._get_symbols_dict(), timeout=5)
