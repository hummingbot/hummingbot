import asyncio
import re
import ujson
import unittest

import hummingbot.connector.exchange.binance.binance_constants as CONSTANTS
import hummingbot.connector.exchange.binance.binance_utils as utils

from aioresponses.core import aioresponses
from binance.client import Client as BinanceClient
from typing import (
    Any,
    Dict,
    Optional,
)
from unittest.mock import AsyncMock, patch

from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.connector.exchange.binance.binance_api_user_stream_data_source import BinanceAPIUserStreamDataSource
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class MockBinanceClient(BinanceClient):

    def __init__(self, api_key: str, *_):
        self._api_key: str = api_key

    @property
    def API_KEY(self):
        return self._api_key


class BinanceUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.binance_client = MockBinanceClient(api_key="TEST_API_KEY")
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = BinanceAPIUserStreamDataSource(
            binance_client=self.binance_client,
            domain=self.domain,
            throttler=self.throttler
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _error_response(self) -> Dict[str, Any]:
        resp = {
            "code": "ERROR CODE",
            "msg": "ERROR MESSAGE"
        }

        return resp

    def _user_update_event(self):
        # Balance Update
        resp = {
            "e": "balanceUpdate",
            "E": 1573200697110,
            "a": "BTC",
            "d": "100.00000000",
            "T": 1573200697068
        }
        return ujson.dumps(resp)

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    def test_get_throttler_instance(self):
        self.assertIsInstance(self.data_source._get_throttler_instance(), AsyncThrottler)

    @aioresponses()
    def test_get_listen_key_log_exception(self, mock_api):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, body=ujson.dumps(self._error_response))

        with self.assertRaises(IOError):
            self.ev_loop.run_until_complete(
                self.data_source.get_listen_key()
            )

    @aioresponses()
    def test_get_listen_key_successful(self, mock_api):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=ujson.dumps(mock_response))

        result: str = self.ev_loop.run_until_complete(self.data_source.get_listen_key())

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    def test_ping_listen_key_log_exception(self, mock_api):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, status=400, body=ujson.dumps(self._error_response()))

        result: bool = self.ev_loop.run_until_complete(
            self.data_source.ping_listen_key(listen_key=self.listen_key)
        )

        self.assertTrue(self._is_logged("WARNING", f"Failed to refresh the listen key {self.listen_key}: {self._error_response()}"))
        self.assertFalse(result)

    @aioresponses()
    def test_ping_listen_key_successful(self, mock_api):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.put(regex_url, body=ujson.dumps({}))

        result: bool = self.ev_loop.run_until_complete(
            self.data_source.ping_listen_key(listen_key=self.listen_key)
        )
        self.assertTrue(result)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource.wait_til_next_tick",
           new_callable=AsyncMock)
    def test_listen_for_user_stream_no_listen_key(self, mock_api, mock_next_tick, mock_ws):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=ujson.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(self.ev_loop, msg_queue)
        )

        msg = self.ev_loop.run_until_complete(msg_queue.get())
        self.assertTrue(msg, self._user_update_event)
