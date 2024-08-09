import asyncio
import json
import re
import time
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.gate_io_spot_candles import GateioSpotCandles, constants as CONSTANTS


class TestGateioSpotCandles(TestCandlesBase):
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
        cls.ex_trading_pair = cls.base_asset + "_" + cls.quote_asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = GateioSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    @aioresponses()
    def test_fetch_candles_raises_exception(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        with self.assertRaises(ValueError, msg="Gate.io REST API does not support fetching more than 10000 candles ago."):
            self.async_run_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                     end_time=self.end_time))

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        self.start_time = int(time.time()) - (CONSTANTS.MAX_CANDLES_AGO - 1) * self.data_feed.interval_in_seconds
        self.end_time = int(time.time())

        candles = self.async_run_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                           end_time=self.end_time))
        self.assertEqual(len(candles), len(data_mock))

    def get_fetch_candles_data_mock(self):
        return [[1685167200, '26728.1', '26736.1', '26718.4', '26718.4', '4.856410775', '129807.73747903012', 0, 0, 0],
                [1685170800, '26718.4', '26758.1', '26709.2', '26746.2', '24.5891110488', '657338.79714685262', 0, 0, 0],
                [1685174400, '26746.2', '26746.2', '26720', '26723.1', '7.5659923741', '202249.7345089816', 0, 0, 0],
                [1685178000, '26723.1', '26723.1', '26710.1', '26723.1', '4.5305391649', '121057.96936704352', 0, 0, 0]]

    def get_candles_rest_data_mock(self):
        return [
            ['1685167200', '129807.73747903012', '26718.4', '26736.1', '26718.4', '26728.1', '4.856410775'],
            ['1685170800', '657338.79714685262', '26746.2', '26758.1', '26709.2', '26718.4', '24.5891110488'],
            ['1685174400', '202249.7345089816', '26723.1', '26746.2', '26720', '26746.2', '7.5659923741'],
            ['1685178000', '121057.96936704352', '26723.1', '26723.1', '26710.1', '26723.1', '4.5305391649']
        ]

    def get_candles_ws_data_mock_1(self):
        data = {
            "time": 1606292600,
            "time_ms": 1606292600376,
            "channel": "spot.candlesticks",
            "event": "update",
            "result": {
                "t": "1606292500",
                "v": "2362.32035",
                "c": "19128.1",
                "h": "19128.1",
                "l": "19128.1",
                "o": "19128.1",
                "n": "1m_BTC_USDT",
                "a": "3.8283"
            }
        }
        return data

    def get_candles_ws_data_mock_2(self):
        data = {
            "time": 1606292600,
            "time_ms": 1606292600376,
            "channel": "spot.candlesticks",
            "event": "update",
            "result": {
                "t": "1606292580",
                "v": "2362.32035",
                "c": "19128.1",
                "h": "19128.1",
                "l": "19128.1",
                "o": "19128.1",
                "n": "1m_BTC_USDT",
                "a": "3.8283"
            }
        }
        return data

    @staticmethod
    def _success_subscription_mock():
        return {}
