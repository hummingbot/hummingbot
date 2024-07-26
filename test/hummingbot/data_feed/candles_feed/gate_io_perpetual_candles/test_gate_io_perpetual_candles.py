import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import GateioPerpetualCandles


class TestGateioPerpetualCandles(TestCandlesBase):
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
        cls.ex_trading_pair = cls.base_asset + "_" + cls.quote_asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = GateioPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.data_feed.quanto_multiplier = 0.0001

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    @staticmethod
    def get_fetch_candles_data_mock():
        return [[1685167200, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0],
                [1685170800, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0],
                [1685174400, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0],
                [1685178000, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0]]

    @staticmethod
    def get_candles_rest_data_mock():
        data = [
            {
                "t": 1685167200,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            }, {
                "t": 1685170800,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            }, {
                "t": 1685174400,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            }, {
                "t": 1685178000,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            },
        ]
        return data

    @staticmethod
    def get_exchange_trading_pair_quanto_multiplier_data_mock():
        data = {"quanto_multiplier": 0.0001}
        return data

    @staticmethod
    def get_candles_ws_data_mock_1():
        data = {
            "time": 1542162490,
            "time_ms": 1542162490123,
            "channel": "futures.candlesticks",
            "event": "update",
            "error": None,
            "result": [
                {
                    "t": 1545129300,
                    "v": 27525555,
                    "c": "95.4",
                    "h": "96.9",
                    "l": "89.5",
                    "o": "94.3",
                    "n": "1m_BTC_USD"
                }
            ]
        }
        return data

    @staticmethod
    def get_candles_ws_data_mock_2():
        data = {
            "time": 1542162490,
            "time_ms": 1542162490123,
            "channel": "futures.candlesticks",
            "event": "update",
            "error": None,
            "result": [
                {
                    "t": 1545139300,
                    "v": 27525555,
                    "c": "95.4",
                    "h": "96.9",
                    "l": "89.5",
                    "o": "94.3",
                    "n": "1m_BTC_USD"
                }
            ]
        }
        return data

    @staticmethod
    def _success_subscription_mock():
        return {}
