import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.backpack_spot_candles import BackpackSpotCandles


class TestBackpackSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDC"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = BackpackSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()

    def get_fetch_candles_data_mock(self):
        return [
            [1672974000.0, '16823.24', '16823.63', '16792.12', '16810.18', '6230.44034', '104737787.3657063', 162086.0, 0., 0.],
            [1672977600.0, '16809.74', '16816.45', '16779.96', '16786.86', '6529.22759', '109693209.6428701', 175249.0, 0., 0.],
            [1672981200.0, '16786.60', '16802.87', '16780.15', '16794.06', '5763.44917', '96775667.5626552', 160778.0, 0., 0.],
            [1672984800.0, '16794.33', '16812.22', '16791.47', '16802.11', '5475.13940', '92000245.5434114', 164303.0, 0., 0.],
        ]

    def get_candles_rest_data_mock(self):
        # Backpack returns a list of objects with UTC ISO-8601 datetime strings for start/end.
        return [
            {"start": "2023-01-06 03:00:00", "end": "2023-01-06 04:00:00", "open": "16823.24", "high": "16823.63",
             "low": "16792.12", "close": "16810.18", "volume": "6230.44034", "quoteVolume": "104737787.3657063",
             "trades": "162086"},
            {"start": "2023-01-06 04:00:00", "end": "2023-01-06 05:00:00", "open": "16809.74", "high": "16816.45",
             "low": "16779.96", "close": "16786.86", "volume": "6529.22759", "quoteVolume": "109693209.6428701",
             "trades": "175249"},
            {"start": "2023-01-06 05:00:00", "end": "2023-01-06 06:00:00", "open": "16786.60", "high": "16802.87",
             "low": "16780.15", "close": "16794.06", "volume": "5763.44917", "quoteVolume": "96775667.5626552",
             "trades": "160778"},
            {"start": "2023-01-06 06:00:00", "end": "2023-01-06 07:00:00", "open": "16794.33", "high": "16812.22",
             "low": "16791.47", "close": "16802.11", "volume": "5475.13940", "quoteVolume": "92000245.5434114",
             "trades": "164303"},
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "stream": "kline.1h.BTC_USDC",
            "data": {
                "e": "kline",
                "E": 1718667728540000,
                "s": "BTC_USDC",
                "t": "2024-06-18T00:00:00",
                "T": "2024-06-18T01:00:00",
                "o": "66477.91",
                "c": "66472.20",
                "h": "66477.91",
                "l": "66468.00",
                "v": "10.75371",
                "n": 246,
                "X": False,
            },
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "stream": "kline.1h.BTC_USDC",
            "data": {
                "e": "kline",
                "E": 1718671328540000,
                "s": "BTC_USDC",
                "t": "2024-06-18T01:00:00",
                "T": "2024-06-18T02:00:00",
                "o": "66472.20",
                "c": "66480.00",
                "h": "66490.00",
                "l": "66470.00",
                "v": "8.12345",
                "n": 199,
                "X": False,
            },
        }

    @staticmethod
    def _success_subscription_mock():
        return {}

    def test_empty_ws_candle_is_skipped(self):
        # Buckets with no trades arrive with null OHLC and must be ignored.
        empty = {"data": {"e": "kline", "s": "BTC_USDC", "t": "2024-06-18T00:00:00", "T": "2024-06-18T01:00:00",
                          "o": None, "c": None, "h": None, "l": None, "v": None, "n": 0, "X": True}}
        self.assertIsNone(self.data_feed._parse_websocket_message(empty))

    def test_ws_subscription_payload(self):
        payload = self.data_feed.ws_subscription_payload()
        self.assertEqual(payload, {"method": "SUBSCRIBE", "params": [f"kline.{self.interval}.{self.ex_trading_pair}"]})

    def test_ws_quote_volume_estimated_from_volume_and_close(self):
        # Backpack's WS kline stream omits quote volume; we approximate it as volume * close.
        msg = self.get_candles_ws_data_mock_1()
        parsed = self.data_feed._parse_websocket_message(msg)
        expected = float(msg["data"]["v"]) * float(msg["data"]["c"])
        self.assertAlmostEqual(parsed["quote_asset_volume"], expected)
        self.assertEqual(parsed["taker_buy_base_volume"], 0.)
        self.assertEqual(parsed["taker_buy_quote_volume"], 0.)
