import asyncio
import json
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.hyperliquid_perpetual_candles import (
    HyperliquidPerpetualCandles,
    constants as CONSTANTS,
)


class TestHyperliquidPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = HyperliquidPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1718895600.0, '64942.0', '65123.0', '64812.0', '64837.0', '190.58479', 0.0, 1789, 0.0, 0.0],
                [1718899200.0, '64837.0', '64964.0', '64564.0', '64898.0', '271.68638', 0.0, 2296, 0.0, 0.0],
                [1718902800.0, '64900.0', '65034.0', '64714.0', '64997.0', '104.80095', 0.0, 1229, 0.0, 0.0],
                [1718906400.0, '64999.0', '65244.0', '64981.0', '65157.0', '158.51753', 0.0, 1598, 0.0, 0.0],
                [1718910000.0, '65153.0', '65153.0', '64882.0', '65095.0', '209.75558', 0.0, 1633, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return [
            {
                "t": 1718895600000,
                "T": 1718899199999,
                "s": "BTC",
                "i": "1h",
                "o": "64942.0",
                "c": "64837.0",
                "h": "65123.0",
                "l": "64812.0",
                "v": "190.58479",
                "n": 1789
            },
            {
                "t": 1718899200000,
                "T": 1718902799999,
                "s": "BTC",
                "i": "1h",
                "o": "64837.0",
                "c": "64898.0",
                "h": "64964.0",
                "l": "64564.0",
                "v": "271.68638",
                "n": 2296
            },
            {
                "t": 1718902800000,
                "T": 1718906399999,
                "s": "BTC",
                "i": "1h",
                "o": "64900.0",
                "c": "64997.0",
                "h": "65034.0",
                "l": "64714.0",
                "v": "104.80095",
                "n": 1229
            },
            {
                "t": 1718906400000,
                "T": 1718909999999,
                "s": "BTC",
                "i": "1h",
                "o": "64999.0",
                "c": "65157.0",
                "h": "65244.0",
                "l": "64981.0",
                "v": "158.51753",
                "n": 1598
            },
            {
                "t": 1718910000000,
                "T": 1718913599999,
                "s": "BTC",
                "i": "1h",
                "o": "65153.0",
                "c": "65095.0",
                "h": "65153.0",
                "l": "64882.0",
                "v": "209.75558",
                "n": 1633
            }
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718914860000,
                "T": 1718914919999,
                "s": "BTC",
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
                "s": "BTC",
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

        resp = self.run_async_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    @aioresponses()
    def test_ping_pong(self, mock_api):
        self.assertEqual(self.data_feed._ping_payload, CONSTANTS.PING_PAYLOAD)
        self.assertEqual(self.data_feed._ping_timeout, CONSTANTS.PING_TIMEOUT)


class TestHyperliquidPerpetualCandlesHIP3(TestCandlesBase):
    """Tests for HIP-3 market support (e.g., xyz:XYZ100-USD)"""
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "xyz:XYZ100"
        cls.quote_asset = "USD"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}".replace(":", "")
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = HyperliquidPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1718895600.0, '100.0', '105.0', '99.0', '102.0', '1000.0', 0.0, 500, 0.0, 0.0],
                [1718899200.0, '102.0', '108.0', '101.0', '106.0', '1200.0', 0.0, 600, 0.0, 0.0],
                [1718902800.0, '106.0', '110.0', '104.0', '109.0', '900.0', 0.0, 450, 0.0, 0.0],
                [1718906400.0, '109.0', '112.0', '107.0', '111.0', '1100.0', 0.0, 550, 0.0, 0.0],
                [1718910000.0, '111.0', '115.0', '110.0', '114.0', '1300.0', 0.0, 650, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return [
            {"t": 1718895600000, "T": 1718899199999, "s": "xyz:XYZ100", "i": "1h",
             "o": "100.0", "c": "102.0", "h": "105.0", "l": "99.0", "v": "1000.0", "n": 500},
            {"t": 1718899200000, "T": 1718902799999, "s": "xyz:XYZ100", "i": "1h",
             "o": "102.0", "c": "106.0", "h": "108.0", "l": "101.0", "v": "1200.0", "n": 600},
            {"t": 1718902800000, "T": 1718906399999, "s": "xyz:XYZ100", "i": "1h",
             "o": "106.0", "c": "109.0", "h": "110.0", "l": "104.0", "v": "900.0", "n": 450},
            {"t": 1718906400000, "T": 1718909999999, "s": "xyz:XYZ100", "i": "1h",
             "o": "109.0", "c": "111.0", "h": "112.0", "l": "107.0", "v": "1100.0", "n": 550},
            {"t": 1718910000000, "T": 1718913599999, "s": "xyz:XYZ100", "i": "1h",
             "o": "111.0", "c": "114.0", "h": "115.0", "l": "110.0", "v": "1300.0", "n": 650},
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718914860000, "T": 1718914919999, "s": "xyz:XYZ100", "i": "1h",
                "o": "114.0", "c": "115.0", "h": "116.0", "l": "113.0", "v": "500.0", "n": 100
            }
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718918460000, "T": 1718922059999, "s": "xyz:XYZ100", "i": "1h",
                "o": "115.0", "c": "118.0", "h": "120.0", "l": "114.0", "v": "600.0", "n": 120
            }
        }

    @staticmethod
    def _success_subscription_mock():
        return {}

    def test_hip3_base_asset_extraction(self):
        """Test that HIP-3 trading pair correctly extracts the base asset with dex prefix"""
        self.assertEqual(self.data_feed._base_asset, "xyz:XYZ100")

    def test_hip3_rest_payload_format(self):
        """Test that HIP-3 markets format the coin correctly in REST payload"""
        payload = self.data_feed._rest_payload(start_time=1000, end_time=2000)
        # HIP-3 format should be lowercase dex prefix: "xyz:XYZ100"
        self.assertEqual(payload["req"]["coin"], "xyz:XYZ100")
        self.assertEqual(payload["type"], "candleSnapshot")

    def test_hip3_ws_subscription_payload_format(self):
        """Test that HIP-3 markets format the coin correctly in WS subscription"""
        payload = self.data_feed.ws_subscription_payload()
        # HIP-3 format should be lowercase dex prefix: "xyz:XYZ100"
        self.assertEqual(payload["subscription"]["coin"], "xyz:XYZ100")
        self.assertEqual(payload["subscription"]["type"], "candle")

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        """Test fetching candles for HIP-3 market (overrides base test)"""
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.post(url=regex_url, body=json.dumps(data_mock))

        resp = self.run_async_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    @aioresponses()
    def test_fetch_candles_hip3(self, mock_api):
        """Test fetching candles for HIP-3 market"""
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.post(url=regex_url, body=json.dumps(data_mock))

        resp = self.run_async_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    def test_hip3_name_property(self):
        """Test that the name property includes the full HIP-3 trading pair"""
        expected_name = f"hyperliquid_perpetual_{self.trading_pair}"
        self.assertEqual(self.data_feed.name, expected_name)

    def test_get_exchange_trading_pair(self):
        """Override: HIP-3 markets keep the colon but remove the dash"""
        result = self.data_feed.get_exchange_trading_pair(self.trading_pair)
        # xyz:XYZ100-USD -> xyz:XYZ100USD
        self.assertEqual(result, "xyz:XYZ100USD")


class TestHyperliquidPerpetualCandlesUpperCaseHIP3(TestCandlesBase):
    """Tests for HIP-3 market with uppercase dex prefix (e.g., XYZ:AAPL-USD)"""
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "XYZ:AAPL"
        cls.quote_asset = "USD"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}".replace(":", "")
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = HyperliquidPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def get_fetch_candles_data_mock(self):
        return [[1718895600.0, '150.0', '155.0', '148.0', '152.0', '2000.0', 0.0, 800, 0.0, 0.0],
                [1718899200.0, '152.0', '158.0', '150.0', '156.0', '2200.0', 0.0, 900, 0.0, 0.0],
                [1718902800.0, '156.0', '160.0', '154.0', '159.0', '1800.0', 0.0, 700, 0.0, 0.0],
                [1718906400.0, '159.0', '162.0', '157.0', '161.0', '2100.0', 0.0, 850, 0.0, 0.0],
                [1718910000.0, '161.0', '165.0', '160.0', '164.0', '2400.0', 0.0, 950, 0.0, 0.0]]

    def get_candles_rest_data_mock(self):
        return [
            {"t": 1718895600000, "T": 1718899199999, "s": "xyz:AAPL", "i": "1h",
             "o": "150.0", "c": "152.0", "h": "155.0", "l": "148.0", "v": "2000.0", "n": 800},
            {"t": 1718899200000, "T": 1718902799999, "s": "xyz:AAPL", "i": "1h",
             "o": "152.0", "c": "156.0", "h": "158.0", "l": "150.0", "v": "2200.0", "n": 900},
            {"t": 1718902800000, "T": 1718906399999, "s": "xyz:AAPL", "i": "1h",
             "o": "156.0", "c": "159.0", "h": "160.0", "l": "154.0", "v": "1800.0", "n": 700},
            {"t": 1718906400000, "T": 1718909999999, "s": "xyz:AAPL", "i": "1h",
             "o": "159.0", "c": "161.0", "h": "162.0", "l": "157.0", "v": "2100.0", "n": 850},
            {"t": 1718910000000, "T": 1718913599999, "s": "xyz:AAPL", "i": "1h",
             "o": "161.0", "c": "164.0", "h": "165.0", "l": "160.0", "v": "2400.0", "n": 950},
        ]

    def get_candles_ws_data_mock_1(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718914860000, "T": 1718914919999, "s": "xyz:AAPL", "i": "1h",
                "o": "164.0", "c": "165.0", "h": "166.0", "l": "163.0", "v": "700.0", "n": 150
            }
        }

    def get_candles_ws_data_mock_2(self):
        return {
            "channel": "candle",
            "data": {
                "t": 1718918460000, "T": 1718922059999, "s": "xyz:AAPL", "i": "1h",
                "o": "165.0", "c": "168.0", "h": "170.0", "l": "164.0", "v": "800.0", "n": 180
            }
        }

    @staticmethod
    def _success_subscription_mock():
        return {}

    def test_hip3_uppercase_rest_payload_format(self):
        """Test that uppercase HIP-3 dex prefix is converted to lowercase in REST payload"""
        payload = self.data_feed._rest_payload(start_time=1000, end_time=2000)
        # Uppercase XYZ should be converted to lowercase xyz
        self.assertEqual(payload["req"]["coin"], "xyz:AAPL")

    def test_hip3_uppercase_ws_subscription_payload_format(self):
        """Test that uppercase HIP-3 dex prefix is converted to lowercase in WS subscription"""
        payload = self.data_feed.ws_subscription_payload()
        # Uppercase XYZ should be converted to lowercase xyz
        self.assertEqual(payload["subscription"]["coin"], "xyz:AAPL")

    @aioresponses()
    def test_fetch_candles(self, mock_api):
        """Test fetching candles for HIP-3 market with uppercase dex prefix (overrides base test)"""
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.post(url=regex_url, body=json.dumps(data_mock))

        resp = self.run_async_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    @aioresponses()
    def test_fetch_candles_hip3_uppercase(self, mock_api):
        """Test fetching candles for HIP-3 market with uppercase dex prefix"""
        regex_url = re.compile(f"^{self.data_feed.candles_url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_rest_data_mock()
        mock_api.post(url=regex_url, body=json.dumps(data_mock))

        resp = self.run_async_with_timeout(self.data_feed.fetch_candles(start_time=self.start_time,
                                                                        end_time=self.end_time))

        self.assertEqual(resp.shape[0], len(self.get_fetch_candles_data_mock()))
        self.assertEqual(resp.shape[1], 10)

    def test_get_exchange_trading_pair(self):
        """Override: HIP-3 markets keep the colon but remove the dash"""
        result = self.data_feed.get_exchange_trading_pair(self.trading_pair)
        # XYZ:AAPL-USD -> XYZ:AAPLUSD
        self.assertEqual(result, "XYZ:AAPLUSD")
