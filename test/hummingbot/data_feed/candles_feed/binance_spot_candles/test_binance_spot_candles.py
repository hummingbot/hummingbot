import asyncio
import json
import re
import unittest
from typing import Awaitable
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.data_feed.candles_feed.binance_spot_candles import BinanceCandlesFeed, constants as CONSTANTS


class TestBinanceCandlesFeed(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.interval = "1h"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset

    def setUp(self) -> None:
        super().setUp()
        self.mocking_assistant = NetworkMockingAssistant()
        self.data_feed = BinanceCandlesFeed(trading_pair=self.trading_pair, interval=self.interval)

        self.log_records = []
        self.data_feed.logger().setLevel(1)
        self.data_feed.logger().addHandler(self)

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(
            record.levelname == log_level and record.getMessage() == message for
            record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def get_candles_data_mock(self):
        data = [
            [
                1672981200000,
                "16823.24000000",
                "16823.63000000",
                "16792.12000000",
                "16810.18000000",
                "6230.44034000",
                1672984799999,
                "104737787.36570630",
                162086,
                "3058.60695000",
                "51418990.63131130",
                "0"
            ],
            [
                1672984800000,
                "16809.74000000",
                "16816.45000000",
                "16779.96000000",
                "16786.86000000",
                "6529.22759000",
                1672988399999,
                "109693209.64287010",
                175249,
                "3138.11977000",
                "52721850.46080600",
                "0"
            ],
            [
                1672988400000,
                "16786.60000000",
                "16802.87000000",
                "16780.15000000",
                "16794.06000000",
                "5763.44917000",
                1672991999999,
                "96775667.56265520",
                160778,
                "3080.59468000",
                "51727251.37008490",
                "0"
            ],
            [
                1672992000000,
                "16794.33000000",
                "16812.22000000",
                "16791.47000000",
                "16802.11000000",
                "5475.13940000",
                1672995599999,
                "92000245.54341140",
                164303,
                "2761.40926000",
                "46400964.30558100",
                "0"
            ],
        ]

        return data

    @aioresponses()
    def test_fetch_candles(self, mock_api: aioresponses):
        start_time = 1672981200000
        end_time = 1672992000000
        url = f"{CONSTANTS.REST_URL}{CONSTANTS.CANDLES_ENDPOINT}?endTime={end_time}&interval={self.interval}&limit=500" \
              f"&startTime={start_time}&symbol={self.ex_trading_pair}"
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        data_mock = self.get_candles_data_mock()
        mock_api.get(url=regex_url, body=json.dumps(data_mock))

        resp = self.async_run_with_timeout(self.data_feed.fetch_candles(start_time=start_time, end_time=end_time))

        self.assertEqual(resp.shape[0], len(data_mock))
        self.assertEqual(resp.shape[1], 10)

    def test_candles_empty(self):
        self.assertTrue(self.data_feed.candles.empty)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_subscriptions_subscribes_to_klines(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_klines = {
            "result": None,
            "id": 1
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_klines))

        self.listening_task = self.ev_loop.create_task(self.data_feed.listen_for_subscriptions())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(1, len(sent_subscription_messages))
        expected_kline_subscription = {
            "method": "SUBSCRIBE",
            "params": [f"{self.ex_trading_pair.lower()}@kline_{self.interval}"],
            "id": 1}

        self.assertEqual(expected_kline_subscription, sent_subscription_messages[0])

        self.assertTrue(self.is_logged(
            "INFO",
            "Subscribed to public klines..."
        ))
