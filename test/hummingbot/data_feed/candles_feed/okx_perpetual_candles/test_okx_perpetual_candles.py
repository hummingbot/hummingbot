import asyncio
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.okx_perpetual_candles import OKXPerpetualCandles


class TestOKXPerpetualCandles(TestCandlesBase):
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
        cls.ex_trading_pair = f"{cls.base_asset}-{cls.quote_asset}-SWAP"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = OKXPerpetualCandles(trading_pair=self.trading_pair,
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
                [
                    "1718658000000",
                    "66401",
                    "66734",
                    "66310.1",
                    "66575.3",
                    "201605.6",
                    "2016.056",
                    "134181486.8892",
                    "1"
                ],
                [
                    "1718654400000",
                    "66684",
                    "66765.1",
                    "66171.3",
                    "66400.6",
                    "532566.8",
                    "5325.668",
                    "353728101.5321",
                    "1"
                ],
                [
                    "1718650800000",
                    "67087.1",
                    "67099.8",
                    "66560",
                    "66683.9",
                    "449946.1",
                    "4499.461",
                    "300581935.693",
                    "1"
                ],
                [
                    "1718647200000",
                    "66602",
                    "67320",
                    "66543.3",
                    "67087",
                    "1345995.9",
                    "13459.959",
                    "900743428.1363",
                    "1"
                ]
            ]
        }
        return data

    def get_fetch_candles_data_mock(self):
        return [[1718647200.0, '66602', '67320', '66543.3', '67087', '13459.959', '900743428.1363', 0.0, 0.0, 0.0],
                [1718650800.0, '67087.1', '67099.8', '66560', '66683.9', '4499.461', '300581935.693', 0.0, 0.0, 0.0],
                [1718654400.0, '66684', '66765.1', '66171.3', '66400.6', '5325.668', '353728101.5321', 0.0, 0.0, 0.0],
                [1718658000.0, '66401', '66734', '66310.1', '66575.3', '2016.056', '134181486.8892', 0.0, 0.0, 0.0]]

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
