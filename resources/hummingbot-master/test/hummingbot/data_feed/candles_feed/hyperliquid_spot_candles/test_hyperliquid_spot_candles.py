import asyncio
import json
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.hyperliquid_spot_candles import HyperliquidSpotCandles


class TestHyperliquidSpotC0andles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "HFUN"
        cls.quote_asset = "USDC"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = HyperliquidSpotCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.data_feed._coins_dict = {"USDC": 0, "HFUN": 1}

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1718895600.0, '7.8095', '7.8819', '7.7403', '7.765', '1746.14', 0.0, 267, 0.0, 0.0],
                [1718899200.0, '7.765', '7.7882', '7.711', '7.7418', '2065.26', 0.0, 187, 0.0, 0.0],
                [1718902800.0, '7.7418', '7.765', '7.7418', '7.7478', '1084.02', 0.0, 364, 0.0, 0.0],
                [1718906400.0, '7.747', '7.7646', '7.5655', '7.5872', '3312.84', 0.0, 975, 0.0, 0.0],
                [1718910000.0, '7.5887', '7.5937', '7.5276', '7.5379', '3316.37', 0.0, 934, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return [
            {
                "t": 1718895600000,
                "T": 1718899199999,
                "s": "@1",
                "i": "1h",
                "o": "7.8095",
                "c": "7.765",
                "h": "7.8819",
                "l": "7.7403",
                "v": "1746.14",
                "n": 267
            },
            {
                "t": 1718899200000,
                "T": 1718902799999,
                "s": "@1",
                "i": "1h",
                "o": "7.765",
                "c": "7.7418",
                "h": "7.7882",
                "l": "7.711",
                "v": "2065.26",
                "n": 187
            },
            {
                "t": 1718902800000,
                "T": 1718906399999,
                "s": "@1",
                "i": "1h",
                "o": "7.7418",
                "c": "7.7478",
                "h": "7.765",
                "l": "7.7418",
                "v": "1084.02",
                "n": 364
            },
            {
                "t": 1718906400000,
                "T": 1718909999999,
                "s": "@1",
                "i": "1h",
                "o": "7.747",
                "c": "7.5872",
                "h": "7.7646",
                "l": "7.5655",
                "v": "3312.84",
                "n": 975
            },
            {
                "t": 1718910000000,
                "T": 1718913599999,
                "s": "@1",
                "i": "1h",
                "o": "7.5887",
                "c": "7.5379",
                "h": "7.5937",
                "l": "7.5276",
                "v": "3316.37",
                "n": 934
            }
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718914860000,
                "T": 1718914919999,
                "s": "@1",
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
                "s": "@1",
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

    @staticmethod
    def get_universe_data_mock():
        return {'universe': [{'tokens': [1, 0], 'name': 'PURR/USDC', 'index': 0, 'isCanonical': True}, {'tokens': [2, 0], 'name': '@1', 'index': 1, 'isCanonical': False}, {'tokens': [3, 0], 'name': '@2', 'index': 2, 'isCanonical': False}, {'tokens': [4, 0], 'name': '@3', 'index': 3, 'isCanonical': False}, {'tokens': [5, 0], 'name': '@4', 'index': 4, 'isCanonical': False}, {'tokens': [6, 0], 'name': '@5', 'index': 5, 'isCanonical': False}, {'tokens': [7, 0], 'name': '@6', 'index': 6, 'isCanonical': False}, {'tokens': [8, 0], 'name': '@7', 'index': 7, 'isCanonical': False}, {'tokens': [9, 0], 'name': '@8', 'index': 8, 'isCanonical': False}, {'tokens': [10, 0], 'name': '@9', 'index': 9, 'isCanonical': False}, {'tokens': [11, 0], 'name': '@10', 'index': 10, 'isCanonical': False}, {'tokens': [12, 0], 'name': '@11', 'index': 11, 'isCanonical': False}, {'tokens': [13, 0], 'name': '@12', 'index': 12, 'isCanonical': False}, {'tokens': [14, 0], 'name': '@13', 'index': 13, 'isCanonical': False}, {'tokens': [15, 0], 'name': '@14', 'index': 14, 'isCanonical': False}, {'tokens': [16, 0], 'name': '@15', 'index': 15, 'isCanonical': False}, {'tokens': [17, 0], 'name': '@16', 'index': 16, 'isCanonical': False}, {'tokens': [18, 0], 'name': '@17', 'index': 17, 'isCanonical': False}, {'tokens': [19, 0], 'name': '@18', 'index': 18, 'isCanonical': False}, {'tokens': [20, 0], 'name': '@19', 'index': 19, 'isCanonical': False}], 'tokens': [{'name': 'USDC', 'szDecimals': 8, 'weiDecimals': 8, 'index': 0, 'tokenId': '0x6d1e7cde53ba9467b783cb7c530ce054', 'isCanonical': True}, {'name': 'PURR', 'szDecimals': 0, 'weiDecimals': 5, 'index': 1, 'tokenId': '0xc1fb593aeffbeb02f85e0308e9956a90', 'isCanonical': True}, {'name': 'HFUN', 'szDecimals': 2, 'weiDecimals': 8, 'index': 2, 'tokenId': '0xbaf265ef389da684513d98d68edf4eae', 'isCanonical': False}, {'name': 'LICK', 'szDecimals': 0, 'weiDecimals': 5, 'index': 3, 'tokenId': '0xba3aaf468f793d9b42fd3328e24f1de9', 'isCanonical': False}, {'name': 'MANLET', 'szDecimals': 0, 'weiDecimals': 5, 'index': 4, 'tokenId': '0xe9ced9225d2a69ccc8d6a5b224524b99', 'isCanonical': False}, {'name': 'JEFF', 'szDecimals': 0, 'weiDecimals': 5, 'index': 5, 'tokenId': '0xfcf28885456bf7e7cbe5b7a25407c5bc', 'isCanonical': False}, {'name': 'SIX', 'szDecimals': 2, 'weiDecimals': 8, 'index': 6, 'tokenId': '0x50a9391b4a40caffbe8b16303b95a0c1', 'isCanonical': False}, {'name': 'WAGMI', 'szDecimals': 2, 'weiDecimals': 8, 'index': 7, 'tokenId': '0x649efea44690cf88d464f512bc7e2818', 'isCanonical': False}, {'name': 'CAPPY', 'szDecimals': 0, 'weiDecimals': 5, 'index': 8, 'tokenId': '0x3f8abf62220007cc7ab6d33ef2963d88', 'isCanonical': False}, {'name': 'POINTS', 'szDecimals': 0, 'weiDecimals': 5, 'index': 9, 'tokenId': '0xbb03842e1f71ed27ed8fa012b29affd4', 'isCanonical': False}, {'name': 'TRUMP', 'szDecimals': 2, 'weiDecimals': 7, 'index': 10, 'tokenId': '0x368cb581f0d51e21aa19996d38ffdf6f', 'isCanonical': False}, {'name': 'GMEOW', 'szDecimals': 0, 'weiDecimals': 8, 'index': 11, 'tokenId': '0x07615193eaa63d1da6feda6e0ac9e014', 'isCanonical': False}, {'name': 'PEPE', 'szDecimals': 2, 'weiDecimals': 7, 'index': 12, 'tokenId': '0x79b6e1596ea0deb2e6912ff8392c9325', 'isCanonical': False}, {'name': 'XULIAN', 'szDecimals': 0, 'weiDecimals': 5, 'index': 13, 'tokenId': '0x6cc648be7e4c38a8c7fcd8bfa6714127', 'isCanonical': False}, {'name': 'RUG', 'szDecimals': 0, 'weiDecimals': 5, 'index': 14, 'tokenId': '0x4978f3f49f30776d9d7397b873223c2d', 'isCanonical': False}, {'name': 'ILIENS', 'szDecimals': 0, 'weiDecimals': 5, 'index': 15, 'tokenId': '0xa74984ea379be6d899c1bf54db923604', 'isCanonical': False}, {'name': 'FUCKY', 'szDecimals': 2, 'weiDecimals': 8, 'index': 16, 'tokenId': '0x7de5b7a8c115edf0174333446ba0ea78', 'isCanonical': False}, {'name': 'CZ', 'szDecimals': 2, 'weiDecimals': 7, 'index': 17, 'tokenId': '0x3b5ff6cb91f71032578b53960090adfb', 'isCanonical': False}, {'name': 'BAGS', 'szDecimals': 0, 'weiDecimals': 5, 'index': 18, 'tokenId': '0x979978fd8cb07141f97dcab921ba697a', 'isCanonical': False}, {'name': 'ANSEM', 'szDecimals': 0, 'weiDecimals': 5, 'index': 19, 'tokenId': '0xa96cfac10eaecba151f646c5cb4c5507', 'isCanonical': False}, {'name': 'TATE', 'szDecimals': 0, 'weiDecimals': 5, 'index': 20, 'tokenId': '0xfba416cad5d8944e954deb6bfb2a8672', 'isCanonical': False}, {'name': 'FUN', 'szDecimals': 1, 'weiDecimals': 6, 'index': 21, 'tokenId': '0x3dc9f93c39ddd9f0182ad1e584bae0d4', 'isCanonical': False}, {'name': 'SUCKY', 'szDecimals': 0, 'weiDecimals': 5, 'index': 22, 'tokenId': '0xfd2ac85551ac85d3f04369e296ed8cd3', 'isCanonical': False}, {'name': 'BIGBEN', 'szDecimals': 2, 'weiDecimals': 8, 'index': 23, 'tokenId': '0x231f2a687770b13fe12adb1f339ff722', 'isCanonical': False}, {'name': 'KOBE', 'szDecimals': 0, 'weiDecimals': 5, 'index': 24, 'tokenId': '0x0d2556646326733d86c3fc4c2fa22ad4', 'isCanonical': False}, {'name': 'VEGAS', 'szDecimals': 2, 'weiDecimals': 8, 'index': 25, 'tokenId': '0xb693d596cd02f5f38e532e647bb43b69', 'isCanonical': False}]}

    @aioresponses()
    def test_initialize_coins_dict(self, mock_api):
        url = self.data_feed.rest_url
        mock_api.post(url=url, payload=self.get_universe_data_mock())
        self.async_run_with_timeout(self.data_feed._initialize_coins_dict())
        self.assertEqual(self.data_feed._universe, self.get_universe_data_mock())
