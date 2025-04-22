import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.dexalot_spot_candles import DexalotSpotCandles


class TestDexalotSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "ALOT"
        cls.quote_asset = "USDC"
        cls.interval = "5m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + "/" + cls.quote_asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.start_time = 1734619800
        self.end_time = 1734620700
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = DexalotSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1734619800.0, None, None, None, None, None, 0.0, 0.0, 0.0, 0.0],
                [1734620100.0, '1.0128', '1.0128', '1.0128', '1.0128', '4.94', 0.0, 0.0, 0.0, 0.0],
                [1734620400.0, None, None, None, None, None, 0.0, 0.0, 0.0, 0.0],
                [1734620700.0, '1.0074', '1.0073', '1.0074', '1.0073', '68.91', 0.0, 0.0, 0.0,
                 0.0]]

    def get_candles_rest_data_mock(self):
        return [
            {'pair': 'ALOT/USDC', 'date': '2024-12-19T22:50:00.000Z', 'low': None, 'high': None, 'open': None,
             'close': None, 'volume': None, 'change': None},
            {'pair': 'ALOT/USDC', 'date': '2024-12-19T22:55:00.000Z', 'low': '1.0128', 'high': '1.0128',
             'open': '1.0128', 'close': '1.0128', 'volume': '4.94', 'change': '0.0000'},
            {'pair': 'ALOT/USDC', 'date': '2024-12-19T23:00:00.000Z', 'low': None, 'high': None, 'open': None,
             'close': None, 'volume': None, 'change': None},
            {'pair': 'ALOT/USDC', 'date': '2024-12-19T23:05:00.000Z', 'low': '1.0073', 'high': '1.0074',
             'open': '1.0074', 'close': '1.0073', 'volume': '68.91', 'change': '-0.0001'},
        ]

    def get_candles_ws_data_mock_1(self):
        return {'data': [
            {'date': '2025-01-11T17:25:00Z', 'low': '0.834293', 'high': '0.8343', 'open': '0.834293',
             'close': '0.8343',
             'volume': '74.858252584002608541', 'change': '0.00', 'active': True, 'updated': True}],
            'type': 'liveCandle',
            'pair': 'ALOT/USDC'}

    def get_candles_ws_data_mock_2(self):
        return {'data': [
            {'date': '2025-01-11T17:30:00Z', 'low': '0.834293', 'high': '0.8343', 'open': '0.834293',
             'close': '0.8343',
             'volume': '74.858252584002608541', 'change': '0.00', 'active': True, 'updated': True}],
            'type': 'liveCandle',
            'pair': 'ALOT/USDC'}

    @staticmethod
    def _success_subscription_mock():
        return {'data': 'Dexalot websocket server...', 'type': 'info'}
