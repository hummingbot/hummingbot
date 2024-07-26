import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.mexc_perpetual_candles import MexcPerpetualCandles


class TestMexcPerpetualCandles(TestCandlesBase):
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
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = MexcPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1717632000, 3868.6, 3870, 3860.14, 3862.3, 851390, 32903657.9187, 0.0, 0.0, 0.0],
                [1717635600, 3862.3, 3873.61, 3856.32, 3864.04, 705088, 27251412.0495, 0.0, 0.0, 0.0],
                [1717639200, 3864.04, 3881.99, 3862.3, 3871.27, 608801, 23576631.8815, 0.0, 0.0, 0.0],
                [1717642800, 3871.27, 3876.18, 3862.99, 3864.01, 484966, 18769321.3995, 0.0, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return {
            "success": True,
            "code": 0,
            "data": {
                "time": [
                    1717632000,
                    1717635600,
                    1717639200,
                    1717642800
                ],
                "open": [
                    3868.6,
                    3862.3,
                    3864.04,
                    3871.27
                ],
                "close": [
                    3862.3,
                    3864.04,
                    3871.27,
                    3864.01
                ],
                "high": [
                    3870,
                    3873.61,
                    3881.99,
                    3876.18
                ],
                "low": [
                    3860.14,
                    3856.32,
                    3862.3,
                    3862.99
                ],
                "vol": [
                    851390,
                    705088,
                    608801,
                    484966
                ],
                "amount": [
                    32903657.9187,
                    27251412.0495,
                    23576631.8815,
                    18769321.3995
                ],
                "realOpen": [
                    3868.61,
                    3862.29,
                    3864.04,
                    3871.26
                ],
                "realClose": [
                    3862.3,
                    3864.04,
                    3871.27,
                    3864.01
                ],
                "realHigh": [
                    3870,
                    3873.61,
                    3881.99,
                    3876.18
                ],
                "realLow": [
                    3860.14,
                    3856.32,
                    3862.3,
                    3862.99
                ]
            }
        }

    def get_candles_ws_data_mock_1(self):
        return {
            "symbol": "BTC_USDT",
            "data": {
                "symbol": "BTC_USDT",
                "interval": "Min60",
                "t": 1718751060,
                "o": 65213.5,
                "c": 65210.5,
                "h": 65233.5,
                "l": 65208.5,
                "a": 3344326.96161,
                "q": 512797,
                "ro": 65213.4,
                "rc": 65210.5,
                "rh": 65233.5,
                "rl": 65208.5
            },
            "channel": "push.kline",
            "ts": 1718751106472
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "symbol": "BTC_USDT",
            "data": {
                "symbol": "BTC_USDT",
                "interval": "Min60",
                "t": 1718751061,
                "o": 65213.5,
                "c": 65210.5,
                "h": 65233.5,
                "l": 65208.5,
                "a": 3344326.96161,
                "q": 512797,
                "ro": 65213.4,
                "rc": 65210.5,
                "rh": 65233.5,
                "rl": 65208.5
            },
            "channel": "push.kline",
            "ts": 1718751106472
        }

    @staticmethod
    def _success_subscription_mock():
        return {}
