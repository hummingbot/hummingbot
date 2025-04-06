import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceSpotCandles


class TestBinanceSpotCandles(TestCandlesBase):
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
        self.data_feed = BinanceSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1672981200.0, '16823.24000000', '16823.63000000', '16792.12000000', '16810.18000000', '6230.44034000', '104737787.36570630', 162086, '3058.60695000', '51418990.63131130'],
                [1672984800.0, '16809.74000000', '16816.45000000', '16779.96000000', '16786.86000000', '6529.22759000', '109693209.64287010', 175249, '3138.11977000', '52721850.46080600'],
                [1672988400.0, '16786.60000000', '16802.87000000', '16780.15000000', '16794.06000000', '5763.44917000', '96775667.56265520', 160778, '3080.59468000', '51727251.37008490'],
                [1672992000.0, '16794.33000000', '16812.22000000', '16791.47000000', '16802.11000000', '5475.13940000', '92000245.54341140', 164303, '2761.40926000', '46400964.30558100']]

    def get_candles_rest_data_mock(self):
        data = [
            [
                1672981200000,
                "16823.24000000",
                "16823.63000000",
                "16792.12000000",
                "16810.18000000",
                "6230.44034000",
                1672984799999,
                "104737787.36570630",
                162086,
                "3058.60695000",
                "51418990.63131130",
                "0"
            ],
            [
                1672984800000,
                "16809.74000000",
                "16816.45000000",
                "16779.96000000",
                "16786.86000000",
                "6529.22759000",
                1672988399999,
                "109693209.64287010",
                175249,
                "3138.11977000",
                "52721850.46080600",
                "0"
            ],
            [
                1672988400000,
                "16786.60000000",
                "16802.87000000",
                "16780.15000000",
                "16794.06000000",
                "5763.44917000",
                1672991999999,
                "96775667.56265520",
                160778,
                "3080.59468000",
                "51727251.37008490",
                "0"
            ],
            [
                1672992000000,
                "16794.33000000",
                "16812.22000000",
                "16791.47000000",
                "16802.11000000",
                "5475.13940000",
                1672995599999,
                "92000245.54341140",
                164303,
                "2761.40926000",
                "46400964.30558100",
                "0"
            ],
        ]
        return data

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
