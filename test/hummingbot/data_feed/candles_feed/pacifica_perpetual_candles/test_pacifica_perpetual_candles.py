import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.pacifica_perpetual_candles import PacificaPerpetualCandles


class TestPacificaPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset  # Pacifica uses just the base asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = PacificaPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

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
        Mock REST API response from Pacifica's /kline endpoint.
        Format based on https://docs.pacifica.fi/api-documentation/api/rest-api/markets/get-candle-data
        """
        return {
            "success": True,
            "data": [
                {
                    "t": 1748954160000,  # Start time (ms)
                    "T": 1748954220000,  # End time (ms)
                    "s": "BTC",
                    "i": "1m",
                    "o": "105376.50",
                    "c": "105380.25",
                    "h": "105385.75",
                    "l": "105372.00",
                    "v": "1.25",
                    "n": 25
                },
                {
                    "t": 1748954220000,
                    "T": 1748954280000,
                    "s": "BTC",
                    "i": "1m",
                    "o": "105380.25",
                    "c": "105378.50",
                    "h": "105382.00",
                    "l": "105375.00",
                    "v": "0.85",
                    "n": 18
                },
                {
                    "t": 1748954280000,
                    "T": 1748954340000,
                    "s": "BTC",
                    "i": "1m",
                    "o": "105378.50",
                    "c": "105390.00",
                    "h": "105395.00",
                    "l": "105378.00",
                    "v": "2.15",
                    "n": 32
                },
                {
                    "t": 1748954340000,
                    "T": 1748954400000,
                    "s": "BTC",
                    "i": "1m",
                    "o": "105390.00",
                    "c": "105385.25",
                    "h": "105392.50",
                    "l": "105383.00",
                    "v": "1.45",
                    "n": 21
                }
            ],
            "error": None,
            "code": None
        }

    @staticmethod
    def get_fetch_candles_data_mock():
        """
        Expected parsed candle data in Hummingbot standard format.
        Format: [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades, taker_buy_base_volume, taker_buy_quote_volume]
        """
        return [
            [1748954160.0, 105376.50, 105385.75, 105372.00, 105380.25, 1.25, 0, 25, 0, 0],
            [1748954220.0, 105380.25, 105382.00, 105375.00, 105378.50, 0.85, 0, 18, 0, 0],
            [1748954280.0, 105378.50, 105395.00, 105378.00, 105390.00, 2.15, 0, 32, 0, 0],
            [1748954340.0, 105390.00, 105392.50, 105383.00, 105385.25, 1.45, 0, 21, 0, 0],
        ]

    @staticmethod
    def get_candles_ws_data_mock_1():
        """
        Mock WebSocket candle update message.
        Format based on https://docs.pacifica.fi/api-documentation/api/websocket/subscriptions/candle
        """
        return {
            "channel": "candle",
            "data": {
                "t": 1749052260000,
                "T": 1749052320000,
                "s": "BTC",
                "i": "1m",
                "o": "105400.00",
                "c": "105410.50",
                "h": "105415.00",
                "l": "105398.00",
                "v": "1.75",
                "n": 28
            }
        }

    @staticmethod
    def get_candles_ws_data_mock_2():
        """
        Mock WebSocket candle update message for next candle.
        """
        return {
            "channel": "candle",
            "data": {
                "t": 1749052320000,
                "T": 1749052380000,
                "s": "BTC",
                "i": "1m",
                "o": "105410.50",
                "c": "105405.75",
                "h": "105412.00",
                "l": "105402.00",
                "v": "1.20",
                "n": 22
            }
        }

    @staticmethod
    def _success_subscription_mock():
        """
        Mock successful WebSocket subscription response.
        Pacifica sends a subscription confirmation.
        """
        return {
            "channel": "subscribe",
            "data": {
                "source": "candle",
                "symbol": "BTC",
                "interval": "1m"
            }
        }
