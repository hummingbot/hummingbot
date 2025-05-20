import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.bitmart_perpetual_candles import BitmartPerpetualCandles


class TestBitmartPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "5m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = BitmartPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.data_feed.contract_size = 0.001
        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [
            [1747267200, "103457.8", "103509.9", "103442.5", "103504.3", "147.548", 0., 0., 0., 0.],
            [1747267500, "103504.3", "103524", "103462.9", "103499.7", "83.616", 0., 0., 0., 0.],
            [1747267800, "103504.3", "103524", "103442.9", "103499.7", "83.714", 0., 0., 0., 0.],
            [1747268100, "103504.3", "103544", "103462.9", "103494.7", "83.946", 0., 0., 0., 0.],
        ]

    def get_candles_rest_data_mock(self):
        return {
            "code": 1000,
            "message": "Ok",
            "data": [
                {
                    "timestamp": 1747267200,
                    "open_price": "103457.8",
                    "high_price": "103509.9",
                    "low_price": "103442.5",
                    "close_price": "103504.3",
                    "volume": "147548",
                },
                {
                    "timestamp": 1747267500,
                    "open_price": "103504.3",
                    "high_price": "103524",
                    "low_price": "103462.9",
                    "close_price": "103499.7",
                    "volume": "83616",
                },
                {
                    "timestamp": 1747267800,
                    "open_price": "103504.3",
                    "high_price": "103524",
                    "low_price": "103442.9",
                    "close_price": "103499.7",
                    "volume": "83714",
                },
                {
                    "timestamp": 1747268100,
                    "open_price": "103504.3",
                    "high_price": "103544",
                    "low_price": "103462.9",
                    "close_price": "103494.7",
                    "volume": "83946",
                },
            ]
        }

    def get_candles_ws_data_mock_1(self):
        return {
            'data': {
                'items': [
                    {'c': '1.157',
                     'h': '1.158',
                     'l': '1.1509',
                     'o': '1.1517',
                     'ts': 1747425900,
                     'v': '29572'}
                ],
                'symbol': 'WLDUSDT'
            },
            'group': 'futures/klineBin5m:WLDUSDT'
        }

    def get_candles_ws_data_mock_2(self):
        return {
            'data': {
                'items': [
                    {'c': '1.157',
                     'h': '1.158',
                     'l': '1.1509',
                     'o': '1.157',
                     'ts': 1747426200,
                     'v': '23472'}
                ],
                'symbol': 'WLDUSDT'
            },
            'group': 'futures/klineBin5m:WLDUSDT'
        }

    @staticmethod
    def _success_subscription_mock():
        return {}
