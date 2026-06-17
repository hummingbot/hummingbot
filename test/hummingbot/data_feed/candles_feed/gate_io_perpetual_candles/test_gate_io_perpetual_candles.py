import asyncio
import json
import re
from test.hummingbot.data_feed.candles_feed.test_candles_base import TestCandlesBase
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.gate_io_perpetual_candles import GateioPerpetualCandles, constants as CONSTANTS


class TestGateioPerpetualCandles(TestCandlesBase):
    __test__ = True
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + "_" + cls.quote_asset
        cls.max_records = 150

    def setUp(self) -> None:
        super().setUp()
        self.data_feed = GateioPerpetualCandles(trading_pair=self.trading_pair, interval=self.interval)
        self.data_feed.quanto_multiplier = 0.0001
        self.data_feed._exchange_data_initialized = True  # pre-set to skip initialize_exchange_data API call

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    @staticmethod
    def get_fetch_candles_data_mock():
        return [[1685167200, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0],
                [1685170800, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0],
                [1685174400, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0],
                [1685178000, '1.032', '1.032', '1.032', '1.032', 9.7151, '3580', 0, 0, 0]]

    @staticmethod
    def get_candles_rest_data_mock():
        data = [
            {
                "t": 1685167200,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            }, {
                "t": 1685170800,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            }, {
                "t": 1685174400,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            }, {
                "t": 1685178000,
                "v": 97151,
                "c": "1.032",
                "h": "1.032",
                "l": "1.032",
                "o": "1.032",
                "sum": "3580"
            },
        ]
        return data

    @staticmethod
    def get_exchange_trading_pair_quanto_multiplier_data_mock():
        data = {"quanto_multiplier": 0.0001}
        return data

    @staticmethod
    def get_candles_ws_data_mock_1():
        data = {
            "time": 1542162490,
            "time_ms": 1542162490123,
            "channel": "futures.candlesticks",
            "event": "update",
            "error": None,
            "result": [
                {
                    "t": 1545129300,
                    "v": 27525555,
                    "c": "95.4",
                    "h": "96.9",
                    "l": "89.5",
                    "o": "94.3",
                    "n": "1m_BTC_USD"
                }
            ]
        }
        return data

    @staticmethod
    def get_candles_ws_data_mock_2():
        data = {
            "time": 1542162490,
            "time_ms": 1542162490123,
            "channel": "futures.candlesticks",
            "event": "update",
            "error": None,
            "result": [
                {
                    "t": 1545139300,
                    "v": 27525555,
                    "c": "95.4",
                    "h": "96.9",
                    "l": "89.5",
                    "o": "94.3",
                    "n": "1m_BTC_USD"
                }
            ]
        }
        return data

    @staticmethod
    def _success_subscription_mock():
        return {}

    # ---- initialize_exchange_data tests ----

    async def test_initialize_exchange_data_reuses_connector_trading_rules(self):
        # Backed by a connector: quanto_multiplier comes from the connector's trading rules (stored as
        # the min base amount increment); the contract-info endpoint must NOT be hit.
        self.data_feed.quanto_multiplier = None
        self.data_feed._exchange_data_initialized = False
        connector = MagicMock()
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        connector.trading_rules = {self.trading_pair: MagicMock(min_base_amount_increment=0.0001)}
        self.data_feed.use_connector(connector)
        with patch.object(
            self.data_feed._api_factory, "get_rest_assistant", new_callable=AsyncMock
        ) as mock_rest:
            await self.data_feed.initialize_exchange_data()
            mock_rest.assert_not_called()
        self.assertEqual(self.data_feed.quanto_multiplier, 0.0001)

    @aioresponses()
    async def test_initialize_exchange_data_falls_back_when_rules_not_ready(self, mock_api):
        # Connector present but trading rules not polled yet -> fall back to the contract-info fetch.
        self.data_feed.quanto_multiplier = None
        self.data_feed._exchange_data_initialized = False
        connector = MagicMock()
        connector.exchange_symbol_associated_to_pair = AsyncMock(return_value=self.ex_trading_pair)
        connector.trading_rules = {}
        self.data_feed.use_connector(connector)
        regex_url = re.compile(f"^{CONSTANTS.REST_URL}{CONSTANTS.CONTRACT_INFO_URL.format(contract=self.ex_trading_pair)}")
        mock_api.get(url=regex_url, body=json.dumps({"quanto_multiplier": "0.0005"}))
        await self.data_feed.initialize_exchange_data()
        self.assertEqual(self.data_feed.quanto_multiplier, 0.0005)
