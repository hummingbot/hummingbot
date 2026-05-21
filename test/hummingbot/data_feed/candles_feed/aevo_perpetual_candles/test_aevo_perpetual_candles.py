import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.data_feed.candles_feed.aevo_perpetual_candles import AevoPerpetualCandles, constants as CONSTANTS


class TestAevoPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "ETH"
        cls.quote_asset = "USDC"
        cls.interval = "1m"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}-PERP"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = AevoPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    def get_fetch_candles_data_mock(self):
        return [
            [1718895660.0, 3087.0, 3087.0, 3087.0, 3087.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [1718895720.0, 3089.0, 3089.0, 3089.0, 3089.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [1718895780.0, 3088.0, 3088.0, 3088.0, 3088.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [1718895840.0, 3090.0, 3090.0, 3090.0, 3090.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [1718895900.0, 3091.0, 3091.0, 3091.0, 3091.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]

    @staticmethod
    def get_candles_rest_data_mock():
        return {
            "history": [
                ["1718895900000000000", "3091.0"],
                ["1718895840000000000", "3090.0"],
                ["1718895780000000000", "3088.0"],
                ["1718895720000000000", "3089.0"],
                ["1718895660000000000", "3087.0"],
            ]
        }

    @staticmethod
    def get_candles_ws_data_mock_1():
        return {
            "channel": "ticker-500ms:ETH-PERP",
            "data": {
                "timestamp": "1718895660000000000",
                "tickers": [
                    {
                        "instrument_id": "1",
                        "instrument_name": "ETH-PERP",
                        "instrument_type": "PERPETUAL",
                        "index_price": "3087.1",
                        "mark": {"price": "3087.0"},
                    }
                ],
            },
        }

    @staticmethod
    def get_candles_ws_data_mock_2():
        return {
            "channel": "ticker-500ms:ETH-PERP",
            "data": {
                "timestamp": "1718895720000000000",
                "tickers": [
                    {
                        "instrument_id": "1",
                        "instrument_name": "ETH-PERP",
                        "instrument_type": "PERPETUAL",
                        "index_price": "3089.2",
                        "mark": {"price": "3089.0"},
                    }
                ],
            },
        }

    @staticmethod
    def _success_subscription_mock():
        return {"data": [f"{CONSTANTS.WS_TICKER_CHANNEL}:ETH-PERP"]}

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.get(url=regex_url, payload=data_mock)

        resp = self.run_async_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    def test_ping_pong(self):
        self.assertEqual(self.data_feed._ping_payload, CONSTANTS.PING_PAYLOAD)
        self.assertEqual(self.data_feed._ping_timeout, CONSTANTS.PING_TIMEOUT)
