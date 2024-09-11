import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.bybit_spot_candles import BybitSpotCandles


class TestBybitSpotCandles(TestCandlesBase):
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
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = BybitSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1715162400.0, '62308.69', '62524.28', '62258.76', '62439.82', '421.80928', 0.0, 0.0, 0.0, 0.0], [1715166000.0, '62439.82', '62512.32', '62130.38', '62245.79', '423.537479', 0.0, 0.0, 0.0, 0.0], [1715169600.0, '62245.79', '62458.45', '62083.67', '62236.73', '603.163403', 0.0, 0.0, 0.0, 0.0], [1715173200.0, '62236.73', '62466.32', '61780.77', '62440.14', '907.398902', 0.0, 0.0, 0.0, 0.0], [1715176800.0, '62440.14', '62841.64', '62160.72', '62564.68', '706.187244', 0.0, 0.0, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return {'retCode': 0, 'retMsg': 'OK', 'result': {'category': 'spot', 'symbol': 'BTCUSDT', 'list': [['1715176800000', '62440.14', '62841.64', '62160.72', '62564.68', '706.187244', '44137837.83110939'], ['1715173200000', '62236.73', '62466.32', '61780.77', '62440.14', '907.398902', '56295800.30345675'], ['1715169600000', '62245.79', '62458.45', '62083.67', '62236.73', '603.163403', '37546804.69133172'], ['1715166000000', '62439.82', '62512.32', '62130.38', '62245.79', '423.537479', '26383831.12979059'], ['1715162400000', '62308.69', '62524.28', '62258.76', '62439.82', '421.80928', '26322162.21650143']]}, 'retExtInfo': {}, 'time': 1718761678876}

    def get_candles_ws_data_mock_1(self):
        return {
            "topic": "kline.5.BTCUSDT",
            "data": [
                {
                    "start": 1672324800000,
                    "end": 1672325099999,
                    "interval": "5",
                    "open": "16649.5",
                    "close": "16677",
                    "high": "16677",
                    "low": "16608",
                    "volume": "2.081",
                    "turnover": "34666.4005",
                    "confirm": False,
                    "timestamp": 1672324988882
                }
            ],
            "ts": 1672324988882,
            "type": "snapshot"
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "topic": "kline.5.BTCUSDT",
            "data": [
                {
                    "start": 1672328400000,
                    "end": 1672331000000,
                    "interval": "5",
                    "open": "16649.5",
                    "close": "16677",
                    "high": "16677",
                    "low": "16608",
                    "volume": "2.081",
                    "turnover": "34666.4005",
                    "confirm": False,
                    "timestamp": 1672324988882
                }
            ],
            "ts": 1672324988882,
            "type": "snapshot"
        }

    @staticmethod
    def _success_subscription_mock():
        return {}
