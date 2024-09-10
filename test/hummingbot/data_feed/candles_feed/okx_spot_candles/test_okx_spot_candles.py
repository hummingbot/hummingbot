import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.okx_spot_candles import OKXSpotCandles


class TestOKXSpotCandles(TestCandlesBase):
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
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = OKXSpotCandles(trading_pair=self.trading_pair,
                                        interval=self.interval,
                                        max_records=self.max_records)
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    @staticmethod
    def get_candles_rest_data_mock():
        data = {
            "code": "0",
            "msg": "",
            "data": [
                ["1705431600000",
                 "43016",
                 "43183.8",
                 "42946",
                 "43169.7",
                 "404.74017381",
                 "17447600.212916623",
                 "17447600.212916623",
                 "1"],
                ["1705428000000",
                 "43053.3",
                 "43157.4",
                 "42836.5",
                 "43016",
                 "385.88107189",
                 "16589516.212133739",
                 "16589516.212133739",
                 "1"],
                ["1705424400000",
                 "43250.9",
                 "43250.9",
                 "43035.1",
                 "43048.1",
                 "333.55276206",
                 "14383538.301882162",
                 "14383538.301882162",
                 "1"],
                ["1705420800000",
                 "43253.6",
                 "43440.2",
                 "43000",
                 "43250.9",
                 "942.87870026",
                 "40743115.773175484",
                 "40743115.773175484",
                 "1"],
            ]
        }
        return data

    def get_fetch_candles_data_mock(self):
        return [[1705420800.0, '43253.6', '43440.2', '43000', '43250.9', '942.87870026', '40743115.773175484', 0.0, 0.0,
                 0.0],
                [1705424400.0, '43250.9', '43250.9', '43035.1', '43048.1', '333.55276206', '14383538.301882162', 0.0,
                 0.0, 0.0],
                [1705428000.0, '43053.3', '43157.4', '42836.5', '43016', '385.88107189', '16589516.212133739', 0.0, 0.0,
                 0.0],
                [1705431600.0, '43016', '43183.8', '42946', '43169.7', '404.74017381', '17447600.212916623', 0.0, 0.0,
                 0.0]]

    def get_candles_ws_data_mock_1(self):
        data = {
            "arg": {
                "channel": "candle1H",
                "instId": self.ex_trading_pair},
            "data": [
                ["1705420800000",
                 "43253.6",
                 "43440.2",
                 "43000",
                 "43250.9",
                 "942.87870026",
                 "40743115.773175484",
                 "40743115.773175484",
                 "1"]]}
        return data

    def get_candles_ws_data_mock_2(self):
        data = {
            "arg": {
                "channel": "candle1H",
                "instId": self.ex_trading_pair},
            "data": [
                ["1705435200000",
                 "43169.8",
                 "43370",
                 "43168",
                 "43239",
                 "297.60067612",
                 "12874025.740848533",
                 "12874025.740848533",
                 "0"]]}
        return data

    @staticmethod
    def _success_subscription_mock():
        return {}
