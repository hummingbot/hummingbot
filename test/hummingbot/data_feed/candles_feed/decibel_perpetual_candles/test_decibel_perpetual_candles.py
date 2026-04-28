import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.decibel_perpetual_candles import DecibelPerpetualCandles


class TestDecibelPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}/{cls.quote_asset}"  # Decibel uses BTC/USD format
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = DecibelPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    @staticmethod
    def get_candles_rest_data_mock():
        """
        Mock REST API response from Decibel's /api/v1/candlesticks endpoint.
        """
        return {
            "data": [
                {
                    "timestamp": 1748954160000,  # milliseconds
                    "open": 50100.50,
                    "high": 50150.75,
                    "low": 50080.00,
                    "close": 50120.25,
                    "volume": 1.25,
                    "n_trades": 25,
                },
                {
                    "timestamp": 1748954220000,
                    "open": 50120.25,
                    "high": 50135.00,
                    "low": 50110.00,
                    "close": 50125.50,
                    "volume": 0.85,
                    "n_trades": 18,
                },
                {
                    "timestamp": 1748954280000,
                    "open": 50125.50,
                    "high": 50160.00,
                    "low": 50120.00,
                    "close": 50155.00,
                    "volume": 2.15,
                    "n_trades": 32,
                },
                {
                    "timestamp": 1748954340000,
                    "open": 50155.00,
                    "high": 50165.50,
                    "low": 50140.00,
                    "close": 50145.25,
                    "volume": 1.45,
                    "n_trades": 21,
                },
            ],
        }

    @staticmethod
    def get_fetch_candles_data_mock():
        """
        Expected parsed candle data in Hummingbot standard format.
        Format: [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume]
        """
        return [
            [1748954160.0, 50100.50, 50150.75, 50080.00, 50120.25, 1.25, 0, 25, 0, 0],
            [1748954220.0, 50120.25, 50135.00, 50110.00, 50125.50, 0.85, 0, 18, 0, 0],
            [1748954280.0, 50125.50, 50160.00, 50120.00, 50155.00, 2.15, 0, 32, 0, 0],
            [1748954340.0, 50155.00, 50165.50, 50140.00, 50145.25, 1.45, 0, 21, 0, 0],
        ]

    @staticmethod
    def get_candles_ws_data_mock_1():
        """
        Mock WebSocket candle update message.
        """
        return {
            "topic": "market_candlestick:0x1234:1m",
            "data": {
                "timestamp": 1749052260000,
                "open": 50200.00,
                "high": 50215.00,
                "low": 50190.00,
                "close": 50210.50,
                "volume": 1.75,
                "n_trades": 28,
            },
        }

    @staticmethod
    def get_candles_ws_data_mock_2():
        """
        Mock WebSocket candle update message for next candle.
        """
        return {
            "topic": "market_candlestick:0x1234:1m",
            "data": {
                "timestamp": 1749052320000,
                "open": 50210.50,
                "high": 50220.00,
                "low": 50200.00,
                "close": 50205.75,
                "volume": 1.20,
                "n_trades": 22,
            },
        }

    @staticmethod
    def _success_subscription_mock():
        """
        Mock successful WebSocket subscription response.
        """
        return {
            "method": "subscribe",
            "topic": "market_candlestick:0x1234:1m",
        }
