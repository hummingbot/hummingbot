import asyncio
import re
import aiohttp
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

        self.resume_test_event = asyncio.Event()

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

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

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

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

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

    @patch("aiohttp.ClientSession.ws_connect")
    def test_create_websocket_connection_cancelled_when_connecting(self, mock_ws):
        mock_ws.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.ev_loop.run_until_complete(
                self.data_source._create_websocket_connection()
            )

    @patch("aiohttp.ClientSession.ws_connect")
    def test_create_websocket_connection_exception_raised(self, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")

        with self.assertRaises(Exception):
            self.ev_loop.run_until_complete(
                self.data_source._create_websocket_connection()
            )

        self.assertTrue(self._is_logged("NETWORK",
                                        "Unexpected error occured when connecting to WebSocket server. Error: TEST ERROR."))

    @patch("hummingbot.connector.exchange.binance.binance_api_user_stream_data_source.BinanceAPIUserStreamDataSource.ping_listen_key",
           new_callable=AsyncMock)
    def test_manage_listen_key_task_loop_keep_alive_failed(self, mock_ping_listen_key):
        mock_ping_listen_key.side_effect = lambda **_: self._create_return_value_and_unlock_test_with_event(False)

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.ev_loop.create_task(self.data_source._manage_listen_key_task_loop())

        self.ev_loop.run_until_complete(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("ERROR", "Error occurred renewing listen key... "))
        self.assertIsNone(self.data_source._current_listen_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

    @patch("hummingbot.connector.exchange.binance.binance_api_user_stream_data_source.BinanceAPIUserStreamDataSource.ping_listen_key",
           new_callable=AsyncMock)
    def test_manage_listen_key_task_loop_keep_alive_successful(self, mock_ping_listen_key):
        mock_ping_listen_key.side_effect = lambda **_: self._create_return_value_and_unlock_test_with_event(True)

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._current_listen_key = self.listen_key
        self.data_source._listen_key_initialized_event.set()
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.ev_loop.create_task(self.data_source._manage_listen_key_task_loop())

        self.ev_loop.run_until_complete(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("INFO", f"Refreshed listen key {self.listen_key}."))
        self.assertGreater(self.data_source._last_listen_key_ping_ts, 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_get_listen_key_succesful_with_user_update_event(self, mock_api, mock_ws):
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

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_connection_failed(self, mock_api, mock_ws):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=ujson.dumps(mock_response))

        mock_ws.side_effect = lambda **_: self._create_exception_and_unlock_test_with_event(Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(self.ev_loop, msg_queue)
        )

        self.ev_loop.run_until_complete(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("NETWORK",
                                        "Unexpected error occured when connecting to WebSocket server. Error: TEST ERROR."))
        self.assertTrue(self._is_logged("ERROR",
                                        "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_iter_message_throws_exception(self, mock_api, mock_ws):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=ujson.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = lambda: self._create_exception_and_unlock_test_with_event(Exception("TEST ERROR"))
        mock_ws.close.return_value = None

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(self.ev_loop, msg_queue)
        )

        self.ev_loop.run_until_complete(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("NETWORK", "Unexpected error occured when parsing websocket payload. Error: TEST ERROR"))
        self.assertTrue(self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR"))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_handle_ping_frame(self, mock_api, mock_ws):
        url = utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=ujson.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "", aiohttp.WSMsgType.PING)

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(self.ev_loop, msg_queue)
        )

        msg = self.ev_loop.run_until_complete(msg_queue.get())
        self.assertTrue(msg, self._user_update_event)
        self.assertTrue(self._is_logged("DEBUG", "Received PING frame. Sending PONG frame..."))
