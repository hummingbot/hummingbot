import asyncio
import json
import re
import time
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.kraken_spot_candles import KrakenSpotCandles, constants as CONSTANTS


class TestKrakenSpotCandles(TestCandlesBase):
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
        cls.ex_trading_pair = f"XBT{cls.quote_asset}"
        cls.ws_ex_trading_pair = f"XBT/{cls.quote_asset}"
        cls.max_records = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = KrakenSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def _candles_data_mock(self):
        return [[1716127200, '66934.0', '66951.8', '66800.0', '66901.6', '28.50228560', 1906800.0564114398, 0, 0, 0],
                [1716130800, '66901.7', '66989.3', '66551.7', '66669.9', '53.13722207', 3546489.7891181475, 0, 0, 0],
                [1716134400, '66669.9', '66797.5', '66595.1', '66733.4', '40.08457819', 2673585.246863534, 0, 0, 0],
                [1716138000, '66733.4', '66757.4', '66550.0', '66575.4', '21.05882277', 1403517.8905635749, 0, 0, 0]]

    def get_candles_rest_data_mock(self):
        data = {
            "error": [],
            "result": {
                self.ex_trading_pair: [
                    [
                        1716130800,
                        "66934.0",
                        "66951.8",
                        "66800.0",
                        "66901.6",
                        "66899.9",
                        "28.50228560",
                        763
                    ],
                    [
                        1716134400,
                        "66901.7",
                        "66989.3",
                        "66551.7",
                        "66669.9",
                        "66742.1",
                        "53.13722207",
                        1022
                    ],
                    [
                        1716138000,
                        "66669.9",
                        "66797.5",
                        "66595.1",
                        "66733.4",
                        "66698.6",
                        "40.08457819",
                        746
                    ],
                    [
                        1716141600,
                        "66733.4",
                        "66757.4",
                        "66550.0",
                        "66575.4",
                        "66647.5",
                        "21.05882277",
                        702
                    ],
                ],
                "last": 1718715600
            }
        }
        return data

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
        self.assertEqual(len(candles), len(data_mock["result"][self.ex_trading_pair]))

    def get_candles_ws_data_mock_1(self):
        data = [
            42,
            [
                "1542057314.748456",
                "1542057360.435743",
                "3586.70000",
                "3586.70000",
                "3586.60000",
                "3586.60000",
                "3586.68894",
                "0.03373000",
                2
            ],
            "ohlc-60",
            "XBT/USDT"
        ]
        return data

    def get_candles_ws_data_mock_2(self):
        data = [
            42,
            [
                "1542060914.748456",
                "1542060960.435743",
                "3586.70000",
                "3586.70000",
                "3586.60000",
                "3586.60000",
                "3586.68894",
                "0.03373000",
                2
            ],
            "ohlc-60",
            "XBT/USDT"
        ]
        return data

    def _success_subscription_mock(self):
        return {}
