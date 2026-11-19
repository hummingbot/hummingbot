import asyncio
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import CallbackResult, aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.bybit_spot_candles import BybitSpotCandles
from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig


class TestBybitSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = BybitSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1715162400.0, '62308.69', '62524.28', '62258.76', '62439.82', '421.80928', 0.0, 0.0, 0.0, 0.0], [1715166000.0, '62439.82', '62512.32', '62130.38', '62245.79', '423.537479', 0.0, 0.0, 0.0, 0.0], [1715169600.0, '62245.79', '62458.45', '62083.67', '62236.73', '603.163403', 0.0, 0.0, 0.0, 0.0], [1715173200.0, '62236.73', '62466.32', '61780.77', '62440.14', '907.398902', 0.0, 0.0, 0.0, 0.0], [1715176800.0, '62440.14', '62841.64', '62160.72', '62564.68', '706.187244', 0.0, 0.0, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return {'retCode': 0, 'retMsg': 'OK', 'result': {'category': 'spot', 'symbol': 'BTCUSDT', 'list': [['1715176800000', '62440.14', '62841.64', '62160.72', '62564.68', '706.187244', '44137837.83110939'], ['1715173200000', '62236.73', '62466.32', '61780.77', '62440.14', '907.398902', '56295800.30345675'], ['1715169600000', '62245.79', '62458.45', '62083.67', '62236.73', '603.163403', '37546804.69133172'], ['1715166000000', '62439.82', '62512.32', '62130.38', '62245.79', '423.537479', '26383831.12979059'], ['1715162400000', '62308.69', '62524.28', '62258.76', '62439.82', '421.80928', '26322162.21650143']]}, 'retExtInfo': {}, 'time': 1718761678876}

    def get_candles_ws_data_mock_1(self):
        return {
            "topic": "kline.5.BTCUSDT",
            "data": [
                {
                    "start": 1672324800000,
                    "end": 1672325099999,
                    "interval": "5",
                    "open": "16649.5",
                    "close": "16677",
                    "high": "16677",
                    "low": "16608",
                    "volume": "2.081",
                    "turnover": "34666.4005",
                    "confirm": False,
                    "timestamp": 1672324988882
                }
            ],
            "ts": 1672324988882,
            "type": "snapshot"
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "topic": "kline.5.BTCUSDT",
            "data": [
                {
                    "start": 1672328400000,
                    "end": 1672331000000,
                    "interval": "5",
                    "open": "16649.5",
                    "close": "16677",
                    "high": "16677",
                    "low": "16608",
                    "volume": "2.081",
                    "turnover": "34666.4005",
                    "confirm": False,
                    "timestamp": 1672324988882
                }
            ],
            "ts": 1672324988882,
            "type": "snapshot"
        }

    @staticmethod
    def _success_subscription_mock():
        return {}

    def test_get_rest_candles_params_sends_start_and_end(self):
        params = self.data_feed._get_rest_candles_params(start_time=1715162400, end_time=1715176800)

        self.assertEqual(1715162400000, params["start"])
        self.assertEqual(1715176800000, params["end"])
        self.assertNotIn("startTime", params)
        self.assertNotIn("endTime", params)

    @aioresponses()
    async def test_get_historical_candles_returns_a_window_older_than_the_latest_page(self, mock_api):
        # Like the venue: the window comes from start/end (ms), newest 1000 if longer; without them, the latest 1000
        step_ms = 3600 * 1000
        latest_ms = 1792627200000

        def kline_rows(first_ms, count):
            rows = [[str(first_ms + i * step_ms), "100", "101", "99", "100.5", "2", "201"] for i in range(count)]
            return rows[::-1]  # newest first

        def callback(url, **kwargs):
            query = url.query
            if "start" in query and "end" in query:
                first_ms, last_ms = int(query["start"]), int(query["end"])
                count = min((last_ms - first_ms) // step_ms + 1, 1000)
                rows = kline_rows(last_ms - (count - 1) * step_ms, count)
            else:
                rows = kline_rows(latest_ms - 999 * step_ms, 1000)
            return CallbackResult(payload={"retCode": 0, "retMsg": "OK", "result": {"category": "spot", "symbol": "BTCUSDT", "list": rows}})

        mock_api.get(re.compile(f"^{re.escape(self.data_feed.candles_url)}"), callback=callback, repeat=True)

        start_time = (latest_ms - 3000 * step_ms) // 1000
        end_time = start_time + 47 * 3600
        candles = await self.data_feed.get_historical_candles(HistoricalCandlesConfig(
            connector_name="bybit", trading_pair=self.trading_pair, interval=self.interval,
            start_time=start_time, end_time=end_time))

        self.assertEqual([start_time + i * 3600 for i in range(48)], candles["timestamp"].astype(int).tolist())
