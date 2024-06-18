import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

import hummingbot.data_feed.candles_feed.binance_spot_candles.constants as CONSTANTS
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.mexc_spot_candles import MexcSpotCandles


class TestMexcSpotCandles(TestCandlesBase):
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
        cls.max_records = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = MexcSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return

    def get_candles_rest_data_mock(self):
        return [
            [
                1718726400000,
                "64698.66",
                "64868.98",
                "64336",
                "64700.98",
                "575.730117",
                1718730000000,
                "37155549.91"
            ],
            [
                1718730000000,
                "64700.98",
                "64904.91",
                "64400",
                "64603.99",
                "917.852709",
                1718733600000,
                "59373594.99"
            ],
            [
                1718733600000,
                "64603.99",
                "64867.88",
                "64321",
                "64678.01",
                "1007.168584",
                1718737200000,
                "65139730.47"
            ],
            [
                1718737200000,
                "64678.01",
                "64738.83",
                "64066.01",
                "64422.01",
                "862.944706",
                1718740800000,
                "55564341.51"
            ],
            [
                1718740800000,
                "64422.01",
                "64683.84",
                "64178.1",
                "64565.49",
                "552.774673",
                1718744400000,
                "35628336.98"
            ]
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            'e': 'kline',
            'E': 1718667728540,
            's': 'BTCUSDT',
            'k': {
                't': 1718667720000,
                'T': 1718667779999,
                's': 'BTCUSDT',
                'i': '1m',
                'f': 3640284441,
                'L': 3640284686,
                'o': '66477.91000000',
                'c': '66472.20000000',
                'h': '66477.91000000',
                'l': '66468.00000000',
                'v': '10.75371000',
                'n': 246,
                'x': False,
                'q': '714783.46215380',
                'V': '9.29532000',
                'Q': '617844.95963270',
                'B': '0'
            }
        }

    def get_candles_ws_data_mock_2(self):
        return {
            'e': 'kline',
            'E': 1718667728540,
            's': 'BTCUSDT',
            'k': {
                't': 1718671320000,
                'T': 1718674920000,
                's': 'BTCUSDT',
                'i': '1m',
                'f': 3640284441,
                'L': 3640284686,
                'o': '66477.91000000',
                'c': '66472.20000000',
                'h': '66477.91000000',
                'l': '66468.00000000',
                'v': '10.75371000',
                'n': 246,
                'x': False,
                'q': '714783.46215380',
                'V': '9.29532000',
                'Q': '617844.95963270',
                'B': '0'
            }
        }

    @staticmethod
    def _success_subscription_mock():
        return {}
