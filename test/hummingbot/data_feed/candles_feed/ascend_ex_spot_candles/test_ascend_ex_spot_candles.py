import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

import hummingbot.data_feed.candles_feed.okx_spot_candles.constants as CONSTANTS
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.ascend_ex_spot_candles import AscendExSpotCandles


class TestOKXPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"
        cls.max_records = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = AscendExSpotCandles(trading_pair=self.trading_pair,
                                             interval=self.interval,
                                             max_records=self.max_records)
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    @staticmethod
    def get_candles_rest_data_mock():
        data = {
            "code": 0,
            "data": [
                {
                    "m": "bar",
                    "s": "BTC/USDT",
                    "data": {
                        "i": "1",
                        "ts": 1688973840000,
                        "o": "30105.52",
                        "c": "30099.41",
                        "h": "30115.58",
                        "l": "30098.19",
                        "v": "0.13736"
                    }
                },
                {
                    "m": "bar",
                    "s": "BTC/USDT",
                    "data": {
                        "i": "1",
                        "ts": 1688977440000,
                        "o": "30096.84",
                        "c": "30097.88",
                        "h": "30115.67",
                        "l": "30096.84",
                        "v": "0.16625"
                    }
                },
                {
                    "m": "bar",
                    "s": "BTC/USDT",
                    "data": {
                        "i": "1",
                        "ts": 1688981040000,
                        "o": "30092.53",
                        "c": "30087.11",
                        "h": "30115.97",
                        "l": "30087.11",
                        "v": "0.06992"
                    }
                },
                {
                    "m": "bar",
                    "s": "BTC/USDT",
                    "data": {
                        "i": "1",
                        "ts": 1688984640000,
                        "o": "30086.51",
                        "c": "30102.34",
                        "h": "30102.34",
                        "l": "30082.68",
                        "v": "0.14145"
                    }
                },
                {
                    "m": "bar",
                    "s": "BTC/USDT",
                    "data": {
                        "i": "1",
                        "ts": 1688988240000,
                        "o": "30095.93",
                        "c": "30085.25",
                        "h": "30103.04",
                        "l": "30077.94",
                        "v": "0.15819"
                    }
                }
            ]
        }
        return data

    def get_fetch_candles_data_mock(self):
        return [[1688973840.0, '30105.52', '30099.41', '30115.58', '30098.19', 0, '0.13736', 0, 0, 0],
                [1688977440.0, '30096.84', '30115.67', '30096.84', '30097.88', 0, '0.16625', 0, 0, 0],
                [1688981040.0, '30092.53', '30115.97', '30087.11', '30087.11', 0, '0.06992', 0, 0, 0],
                [1688984640.0, '30086.51', '30102.34', '30082.68', '30102.34', 0, '0.14145', 0, 0, 0],
                [1688988240.0, '30095.93', '30103.04', '30077.94', '30085.25', 0, '0.15819', 0, 0, 0],]

    @staticmethod
    def get_candles_ws_data_mock_1():
        data = {
            "m": "bar",
            "s": "BTC/USDT",
            "data": {
                "i": "1",
                "ts": 1575398940000,
                "o": "0.04993",
                "c": "0.04970",
                "h": "0.04993",
                "l": "0.04970",
                "v": "8052"
            }
        }
        return data

    @staticmethod
    def get_candles_ws_data_mock_2():
        data = {
            "m": "bar",
            "s": "BTC/USDT",
            "data": {
                "i": "1",
                "ts": 1575398950000,
                "o": "0.04993",
                "c": "0.04970",
                "h": "0.04993",
                "l": "0.04970",
                "v": "8052"
            }
        }
        return data

    @staticmethod
    def _success_subscription_mock():
        return {}
