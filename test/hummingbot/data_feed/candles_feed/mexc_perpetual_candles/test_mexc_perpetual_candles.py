import asyncio
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import CallbackResult, aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig
from hummingbot.data_feed.candles_feed.mexc_perpetual_candles import MexcPerpetualCandles


class TestMexcPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = MexcPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1717632000, 3868.6, 3870, 3860.14, 3862.3, 851390, 32903657.9187, 0.0, 0.0, 0.0],
                [1717635600, 3862.3, 3873.61, 3856.32, 3864.04, 705088, 27251412.0495, 0.0, 0.0, 0.0],
                [1717639200, 3864.04, 3881.99, 3862.3, 3871.27, 608801, 23576631.8815, 0.0, 0.0, 0.0],
                [1717642800, 3871.27, 3876.18, 3862.99, 3864.01, 484966, 18769321.3995, 0.0, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return {
            "success": True,
            "code": 0,
            "data": {
                "time": [
                    1717632000,
                    1717635600,
                    1717639200,
                    1717642800
                ],
                "open": [
                    3868.6,
                    3862.3,
                    3864.04,
                    3871.27
                ],
                "close": [
                    3862.3,
                    3864.04,
                    3871.27,
                    3864.01
                ],
                "high": [
                    3870,
                    3873.61,
                    3881.99,
                    3876.18
                ],
                "low": [
                    3860.14,
                    3856.32,
                    3862.3,
                    3862.99
                ],
                "vol": [
                    851390,
                    705088,
                    608801,
                    484966
                ],
                "amount": [
                    32903657.9187,
                    27251412.0495,
                    23576631.8815,
                    18769321.3995
                ],
                "realOpen": [
                    3868.61,
                    3862.29,
                    3864.04,
                    3871.26
                ],
                "realClose": [
                    3862.3,
                    3864.04,
                    3871.27,
                    3864.01
                ],
                "realHigh": [
                    3870,
                    3873.61,
                    3881.99,
                    3876.18
                ],
                "realLow": [
                    3860.14,
                    3856.32,
                    3862.3,
                    3862.99
                ]
            }
        }

    def get_candles_ws_data_mock_1(self):
        return {
            "symbol": "BTC_USDT",
            "data": {
                "symbol": "BTC_USDT",
                "interval": "Min60",
                "t": 1718751060,
                "o": 65213.5,
                "c": 65210.5,
                "h": 65233.5,
                "l": 65208.5,
                "a": 3344326.96161,
                "q": 512797,
                "ro": 65213.4,
                "rc": 65210.5,
                "rh": 65233.5,
                "rl": 65208.5
            },
            "channel": "push.kline",
            "ts": 1718751106472
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "symbol": "BTC_USDT",
            "data": {
                "symbol": "BTC_USDT",
                "interval": "Min60",
                "t": 1718751061,
                "o": 65213.5,
                "c": 65210.5,
                "h": 65233.5,
                "l": 65208.5,
                "a": 3344326.96161,
                "q": 512797,
                "ro": 65213.4,
                "rc": 65210.5,
                "rh": 65233.5,
                "rl": 65208.5
            },
            "channel": "push.kline",
            "ts": 1718751106472
        }

    @staticmethod
    def _success_subscription_mock():
        return {}

    def test_get_rest_candles_params_sends_start_and_end_in_seconds(self):
        params = self.data_feed._get_rest_candles_params(start_time=1717632000, end_time=1717642800)

        self.assertEqual({"interval": "Min60", "start": 1717632000, "end": 1717642800}, params)

    @aioresponses()
    async def test_get_historical_candles_returns_a_window_older_than_the_latest_page(self, mock_api):
        # Like the venue: the window comes from start/end (seconds), newest 2000 if longer; without them, the latest 2000
        step = 3600
        latest = 1792627200

        def kline(first, count):
            times = [first + i * step for i in range(count)]
            return {"success": True, "code": 0, "data": {
                "time": times, "open": [100.0] * count, "close": [100.5] * count, "high": [101.0] * count,
                "low": [99.0] * count, "vol": [20.0] * count, "amount": [2010.0] * count}}

        def callback(url, **kwargs):
            query = url.query
            if "start" in query and "end" in query:
                first, last = int(query["start"]), int(query["end"])
                count = min((last - first) // step + 1, 2000)
                return CallbackResult(payload=kline(last - (count - 1) * step, count))
            return CallbackResult(payload=kline(latest - 1999 * step, 2000))

        mock_api.get(re.compile(f"^{re.escape(self.data_feed.candles_url)}"), callback=callback, repeat=True)

        start_time = latest - 5000 * step
        end_time = start_time + 47 * step
        candles = await self.data_feed.get_historical_candles(HistoricalCandlesConfig(
            connector_name="mexc_perpetual", trading_pair=self.trading_pair, interval=self.interval,
            start_time=start_time, end_time=end_time))

        self.assertEqual([start_time + i * step for i in range(48)], candles["timestamp"].astype(int).tolist())
