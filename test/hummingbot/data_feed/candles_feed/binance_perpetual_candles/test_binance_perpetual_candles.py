import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.binance_perpetual_candles import BinancePerpetualCandles


class TestBinancePerpetualCandles(TestCandlesBase):
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
        self.data_feed = BinancePerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_candles_rest_data_mock(self):
        data = [
            [
                1718654400000,
                "66661.40",
                "66746.20",
                "66122.30",
                "66376.00",
                "14150.996",
                1718657999999,
                "939449103.58380",
                155369,
                "7106.240",
                "471742093.14380",
                "0"
            ],
            [
                1718658000000,
                "66376.00",
                "66697.00",
                "66280.40",
                "66550.00",
                "4381.088",
                1718661599999,
                "291370566.35900",
                70240,
                "2273.176",
                "151198574.00840",
                "0"
            ],
            [
                1718661600000,
                "66550.00",
                "66686.30",
                "66455.20",
                "66632.40",
                "3495.412",
                1718665199999,
                "232716285.32220",
                52041,
                "1634.229",
                "108805961.31540",
                "0"
            ],
            [
                1718665200000,
                "66632.40",
                "66694.40",
                "66537.00",
                "66537.00",
                "813.988",
                1718668799999,
                "54243407.92930",
                10655,
                "320.268",
                "21346153.24270",
                "0"
            ]
        ]
        return data

    def get_fetch_candles_data_mock(self):
        return [[1718654400.0, '66661.40', '66746.20', '66122.30', '66376.00', '14150.996', '939449103.58380', 155369, '7106.240', '471742093.14380'],
                [1718658000.0, '66376.00', '66697.00', '66280.40', '66550.00', '4381.088', '291370566.35900', 70240, '2273.176', '151198574.00840'],
                [1718661600.0, '66550.00', '66686.30', '66455.20', '66632.40', '3495.412', '232716285.32220', 52041, '1634.229', '108805961.31540'],
                [1718665200.0, '66632.40', '66694.40', '66537.00', '66537.00', '813.988', '54243407.92930', 10655, '320.268', '21346153.24270']]

    def get_candles_ws_data_mock_1(self):
        return {
            "e": "kline",
            "E": 1638747660000,
            "s": "BTCUSDT",
            "k": {
                "t": 1638747660000,
                "T": 1638747719999,
                "s": "BTCUSDT",
                "i": "1m",
                "f": 100,
                "L": 200,
                "o": "0.0010",
                "c": "0.0020",
                "h": "0.0025",
                "l": "0.0015",
                "v": "1000",
                "n": 100,
                "x": False,
                "q": "1.0000",
                "V": "500",
                "Q": "0.500",
                "B": "123456"
            }
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "e": "kline",
            "E": 1638751260000,
            "s": "BTCUSDT",
            "k": {
                "t": 1638751260000,
                "T": 1638754860000,
                "s": "BTCUSDT",
                "i": "1m",
                "f": 100,
                "L": 200,
                "o": "0.0010",
                "c": "0.0020",
                "h": "0.0025",
                "l": "0.0015",
                "v": "1000",
                "n": 100,
                "x": False,
                "q": "1.0000",
                "V": "500",
                "Q": "0.500",
                "B": "123456"
            }
        }

    @staticmethod
    def _success_subscription_mock():
        return {}
