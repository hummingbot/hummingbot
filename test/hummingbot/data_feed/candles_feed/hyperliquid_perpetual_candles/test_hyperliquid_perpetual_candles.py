import asyncio
import json
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.hyperliquid_perpetual_candles import HyperliquidPerpetualCandles


class TestHyperliquidPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = HyperliquidPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1718895600.0, '64942.0', '65123.0', '64812.0', '64837.0', '190.58479', 0.0, 1789, 0.0, 0.0],
                [1718899200.0, '64837.0', '64964.0', '64564.0', '64898.0', '271.68638', 0.0, 2296, 0.0, 0.0],
                [1718902800.0, '64900.0', '65034.0', '64714.0', '64997.0', '104.80095', 0.0, 1229, 0.0, 0.0],
                [1718906400.0, '64999.0', '65244.0', '64981.0', '65157.0', '158.51753', 0.0, 1598, 0.0, 0.0],
                [1718910000.0, '65153.0', '65153.0', '64882.0', '65095.0', '209.75558', 0.0, 1633, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return [
            {
                "t": 1718895600000,
                "T": 1718899199999,
                "s": "BTC",
                "i": "1h",
                "o": "64942.0",
                "c": "64837.0",
                "h": "65123.0",
                "l": "64812.0",
                "v": "190.58479",
                "n": 1789
            },
            {
                "t": 1718899200000,
                "T": 1718902799999,
                "s": "BTC",
                "i": "1h",
                "o": "64837.0",
                "c": "64898.0",
                "h": "64964.0",
                "l": "64564.0",
                "v": "271.68638",
                "n": 2296
            },
            {
                "t": 1718902800000,
                "T": 1718906399999,
                "s": "BTC",
                "i": "1h",
                "o": "64900.0",
                "c": "64997.0",
                "h": "65034.0",
                "l": "64714.0",
                "v": "104.80095",
                "n": 1229
            },
            {
                "t": 1718906400000,
                "T": 1718909999999,
                "s": "BTC",
                "i": "1h",
                "o": "64999.0",
                "c": "65157.0",
                "h": "65244.0",
                "l": "64981.0",
                "v": "158.51753",
                "n": 1598
            },
            {
                "t": 1718910000000,
                "T": 1718913599999,
                "s": "BTC",
                "i": "1h",
                "o": "65153.0",
                "c": "65095.0",
                "h": "65153.0",
                "l": "64882.0",
                "v": "209.75558",
                "n": 1633
            }
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718914860000,
                "T": 1718914919999,
                "s": "BTC",
                "i": "1h",
                "o": "65162.0",
                "c": "65156.0",
                "h": "65162.0",
                "l": "65156.0",
                "v": "0.00296",
                "n": 2
            }
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718918460000,
                "T": 1718922059999,
                "s": "BTC",
                "i": "1h",
                "o": "65162.0",
                "c": "65156.0",
                "h": "65162.0",
                "l": "65156.0",
                "v": "0.00296",
                "n": 2
            }
        }

    @staticmethod
    def _success_subscription_mock():
        return {}

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.post(url=regex_url, body=json.dumps(data_mock))

        resp = self.async_run_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)
