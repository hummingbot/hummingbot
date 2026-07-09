import asyncio
import json
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.grvt_perpetual_candles import GrvtPerpetualCandles


class TestGrvtPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}_Perp"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = GrvtPerpetualCandles(
            trading_pair=self.trading_pair,
            interval=self.interval,
            max_records=self.max_records,
        )
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    @staticmethod
    def get_candles_rest_data_mock():
        return {
            "result": [
                {
                    "open_time": "1718910000000000000",
                    "close_time": "1718913599999999999",
                    "open": "65153.0",
                    "close": "65095.0",
                    "high": "65153.0",
                    "low": "64882.0",
                    "volume_b": "209.75558",
                    "volume_q": "13647890.8421",
                    "trades": 1633,
                    "instrument": "BTC_USDT_Perp",
                },
                {
                    "open_time": "1718906400000000000",
                    "close_time": "1718909999999999999",
                    "open": "64999.0",
                    "close": "65157.0",
                    "high": "65244.0",
                    "low": "64981.0",
                    "volume_b": "158.51753",
                    "volume_q": "10329912.8142",
                    "trades": 1598,
                    "instrument": "BTC_USDT_Perp",
                },
                {
                    "open_time": "1718902800000000000",
                    "close_time": "1718906399999999999",
                    "open": "64900.0",
                    "close": "64997.0",
                    "high": "65034.0",
                    "low": "64714.0",
                    "volume_b": "104.80095",
                    "volume_q": "6806921.2335",
                    "trades": 1229,
                    "instrument": "BTC_USDT_Perp",
                },
                {
                    "open_time": "1718899200000000000",
                    "close_time": "1718902799999999999",
                    "open": "64837.0",
                    "close": "64898.0",
                    "high": "64964.0",
                    "low": "64564.0",
                    "volume_b": "271.68638",
                    "volume_q": "17619952.9012",
                    "trades": 2296,
                    "instrument": "BTC_USDT_Perp",
                },
            ]
        }

    @staticmethod
    def get_fetch_candles_data_mock():
        return [
            [1718899200.0, "64837.0", "64964.0", "64564.0", "64898.0", "271.68638", "17619952.9012", 2296, 0.0, 0.0],
            [1718902800.0, "64900.0", "65034.0", "64714.0", "64997.0", "104.80095", "6806921.2335", 1229, 0.0, 0.0],
            [1718906400.0, "64999.0", "65244.0", "64981.0", "65157.0", "158.51753", "10329912.8142", 1598, 0.0, 0.0],
            [1718910000.0, "65153.0", "65153.0", "64882.0", "65095.0", "209.75558", "13647890.8421", 1633, 0.0, 0.0],
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "stream": "v1.candle",
            "selector": f"{self.ex_trading_pair}@CI_1_H-TRADE",
            "sequence_number": "101",
            "prev_sequence_number": "100",
            "feed": {
                "open_time": "1718910000000000000",
                "close_time": "1718913599999999999",
                "open": "65153.0",
                "close": "65095.0",
                "high": "65153.0",
                "low": "64882.0",
                "volume_b": "209.75558",
                "volume_q": "13647890.8421",
                "trades": 1633,
                "instrument": self.ex_trading_pair,
            },
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "stream": "v1.candle",
            "selector": f"{self.ex_trading_pair}@CI_1_H-TRADE",
            "sequence_number": "102",
            "prev_sequence_number": "101",
            "feed": {
                "open_time": "1718913600000000000",
                "close_time": "1718917199999999999",
                "open": "65095.0",
                "close": "65112.0",
                "high": "65144.0",
                "low": "65001.0",
                "volume_b": "98.4421",
                "volume_q": "6408201.1132",
                "trades": 901,
                "instrument": self.ex_trading_pair,
            },
        }

    @staticmethod
    def _success_subscription_mock():
        return {
            "jsonrpc": "2.0",
            "result": {"subscriptions": ["v1.candle"]},
            "id": 1,
        }

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.post(url=regex_url, body=json.dumps(self.get_candles_rest_data_mock()))

        response = self.run_async_with_timeout(
            self.data_feed.fetch_candles(start_time=int(self.start_time), end_time=int(self.end_time))
        )

        self.assertEqual(response.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(response.shape[1], 10)

    def test_rest_payload(self):
        payload = self.data_feed._rest_payload(start_time=1718899200, end_time=1718902800, limit=1500)

        self.assertEqual(self.ex_trading_pair, payload["instrument"])
        self.assertEqual("CI_1_H", payload["interval"])
        self.assertEqual("TRADE", payload["type"])
        self.assertEqual(str(int(1718899200 * 1e9)), payload["start_time"])
        self.assertEqual(str(int(1718902800 * 1e9)), payload["end_time"])
        self.assertEqual(1000, payload["limit"])

    def test_rest_payload_requests_one_extra_candle_when_end_time_is_present(self):
        payload = self.data_feed._rest_payload(start_time=1718899200, end_time=1718902800, limit=19)

        self.assertEqual(20, payload["limit"])

    def test_ws_subscription_payload(self):
        payload = self.data_feed.ws_subscription_payload()

        self.assertEqual("2.0", payload["jsonrpc"])
        self.assertEqual("subscribe", payload["method"])
        self.assertEqual("v1.candle", payload["params"]["stream"])
        self.assertEqual([f"{self.ex_trading_pair}@CI_1_H-TRADE"], payload["params"]["selectors"])
