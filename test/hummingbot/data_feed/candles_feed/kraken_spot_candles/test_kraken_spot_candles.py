import asyncio
import json
import re
import time
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.data_types import HistoricalCandlesConfig
from hummingbot.data_feed.candles_feed.kraken_spot_candles import KrakenSpotCandles, constants as CONSTANTS


class TestKrakenSpotCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"XBT{cls.quote_asset}"
        cls.ws_ex_trading_pair = f"XBT/{cls.quote_asset}"
        cls.max_records = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = KrakenSpotCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self._time = int(time.time())
        self._interval_in_seconds = 3600

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
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
                        self._time - self._interval_in_seconds * 3,
                        "66934.0",
                        "66951.8",
                        "66800.0",
                        "66901.6",
                        "66899.9",
                        "28.50228560",
                        763
                    ],
                    [
                        self._time - self._interval_in_seconds * 2,
                        "66901.7",
                        "66989.3",
                        "66551.7",
                        "66669.9",
                        "66742.1",
                        "53.13722207",
                        1022
                    ],
                    [
                        self._time - self._interval_in_seconds,
                        "66669.9",
                        "66797.5",
                        "66595.1",
                        "66733.4",
                        "66698.6",
                        "40.08457819",
                        746
                    ],
                    [
                        self._time,
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

    def test_get_rest_candles_params_clamps_ancient_start_time(self):
        """
        Regression test for https://github.com/hummingbot/hummingbot/issues/8208.

        Previously _get_rest_candles_params raised ValueError when start_time was
        older than MAX_CANDLES_AGO intervals ago.  The bug surfaced for 5-minute
        candles when _is_first_candle_not_included_in_rest_request == True caused
        the base class to subtract one extra interval, pushing candles_ago from
        720 to 721 and killing the fill loop permanently.

        The fix silently clamps start_time to the oldest supported value instead
        of raising, so the fill loop can recover and return the most candles
        available.
        """
        interval = "5m"
        feed_5m = KrakenSpotCandles(trading_pair=self.trading_pair, interval=interval)
        interval_in_seconds = feed_5m.interval_in_seconds  # 300

        # A start_time that is 721 intervals in the past (one beyond the limit)
        ancient_start = int(time.time()) - 721 * interval_in_seconds
        params = feed_5m._get_rest_candles_params(start_time=ancient_start)

        max_lookback = int(time.time()) - CONSTANTS.MAX_CANDLES_AGO * interval_in_seconds
        # The clamped since must be >= max_lookback (allow 1-second tolerance for test timing)
        self.assertGreaterEqual(params["since"], max_lookback - 1,
                                "start_time should be clamped to oldest supported value, not the ancient input")
        self.assertLess(ancient_start, max_lookback,
                        "Pre-condition: ancient_start must be older than max_lookback for this test to be meaningful")

    def test_get_rest_candles_params_does_not_alter_recent_start_time(self):
        """A start_time within the supported window must be passed through unchanged."""
        interval = "5m"
        feed_5m = KrakenSpotCandles(trading_pair=self.trading_pair, interval=interval)
        interval_in_seconds = feed_5m.interval_in_seconds

        # 100 intervals ago — well within the 720-candle window
        recent_start = int(time.time()) - 100 * interval_in_seconds
        params = feed_5m._get_rest_candles_params(start_time=recent_start)
        self.assertEqual(recent_start, params["since"])

    def test_get_rest_candles_params_handles_none_start_time(self):
        """Passing start_time=None must not raise and must pass None through to 'since'."""
        params = self.data_feed._get_rest_candles_params(start_time=None)
        self.assertIsNone(params["since"])

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))
        self.start_time = self._time - self._interval_in_seconds * 3
        self.end_time = self._time
        candles = self.run_async_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                           end_time=self.end_time,
                                                                           limit=4))
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
