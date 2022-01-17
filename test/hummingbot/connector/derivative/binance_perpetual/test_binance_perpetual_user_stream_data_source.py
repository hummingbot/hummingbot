import asyncio
import re
import ujson
import unittest
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth

import hummingbot.connector.derivative.binance_perpetual.constants as CONSTANTS

from aioresponses.core import aioresponses
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.binance_perpetual import binance_perpetual_utils as utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_data_source import (
    BinancePerpetualUserStreamDataSource,
)
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class BinancePerpetualUserStreamDataSourceUnitTests(unittest.TestCase):
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
        cls.domain = CONSTANTS.TESTNET_DOMAIN

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.listen_key = "TEST_LISTEN_KEY"
        cls.auth = BinancePerpetualAuth(api_key=cls.api_key,
                                        api_secret=cls.secret_key)

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.data_source = BinancePerpetualUserStreamDataSource(
            auth=self.auth, domain=self.domain, throttler=self.throttler
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mock_done_event = asyncio.Event()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _successful_get_listen_key_response(self) -> str:
        resp = {"listenKey": self.listen_key}
        return ujson.dumps(resp)

    def _error_response(self) -> Dict[str, Any]:
        resp = {"code": "ERROR CODE", "msg": "ERROR MESSAGE"}

        return resp

    def _simulate_user_update_event(self):
        # Order Trade Update
        resp = {
            "e": "ORDER_TRADE_UPDATE",
            "E": 1591274595442,
            "T": 1591274595453,
            "i": "SfsR",
            "o": {
                "s": "BTCUSD_200925",
                "c": "TEST",
                "S": "SELL",
                "o": "TRAILING_STOP_MARKET",
                "f": "GTC",
                "q": "2",
                "p": "0",
                "ap": "0",
                "sp": "9103.1",
                "x": "NEW",
                "X": "NEW",
                "i": 8888888,
                "l": "0",
                "z": "0",
                "L": "0",
                "ma": "BTC",
                "N": "BTC",
                "n": "0",
                "T": 1591274595442,
                "t": 0,
                "rp": "0",
                "b": "0",
                "a": "0",
                "m": False,
                "R": False,
                "wt": "CONTRACT_PRICE",
                "ot": "TRAILING_STOP_MARKET",
                "ps": "LONG",
                "cp": False,
                "AP": "9476.8",
                "cr": "5.0",
                "pP": False,
            },
        }
        return ujson.dumps(resp)

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    def test_get_throttler_instance(self):
        self.assertIsInstance(self.data_source._get_throttler_instance(), AsyncThrottler)

    @aioresponses()
    def test_get_listen_key_exception_raised(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, body=ujson.dumps(self._error_response))

        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source.get_listen_key())

    @aioresponses()
    def test_get_listen_key_successful(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        result: str = self.async_run_with_timeout(self.data_source.get_listen_key())

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    def test_ping_listen_key_failed_log_warning(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, status=400, body=ujson.dumps(self._error_response()))

        self.data_source._current_listen_key = self.listen_key
        result: bool = self.async_run_with_timeout(self.data_source.ping_listen_key())

        self.assertTrue(
            self._is_logged("WARNING", f"Failed to refresh the listen key {self.listen_key}: {self._error_response()}")
        )
        self.assertFalse(result)

    @aioresponses()
    def test_ping_listen_key_successful(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, body=ujson.dumps({}))

        self.data_source._current_listen_key = self.listen_key
        result: bool = self.async_run_with_timeout(self.data_source.ping_listen_key())
        self.assertTrue(result)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_log_exception(self, mock_api, mock_ws):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.side_effect = Exception("TEST ERROR.")

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))
        except asyncio.exceptions.TimeoutError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR.",
            )
        )

    @aioresponses()
    def test_manage_listen_key_task_loop_keep_alive_failed(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(
            regex_url, status=400, body=ujson.dumps(self._error_response()), callback=self._mock_responses_done_callback
        )

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.ev_loop.create_task(self.data_source._manage_listen_key_task_loop())

        self.async_run_with_timeout(self.mock_done_event.wait())

        self.assertTrue(self._is_logged("ERROR", "Error occurred renewing listen key... "))
        self.assertIsNone(self.data_source._current_listen_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

    @aioresponses()
    def test_manage_listen_key_task_loop_keep_alive_successful(self, mock_api):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, body=ujson.dumps({}), callback=self._mock_responses_done_callback)

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.ev_loop.create_task(self.data_source._manage_listen_key_task_loop())

        self.async_run_with_timeout(self.mock_done_event.wait())

        self.assertTrue(self._is_logged("INFO", f"Refreshed listen key {self.listen_key}."))
        self.assertGreater(self.data_source._last_listen_key_ping_ts, 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_create_websocket_connection_failed(self, mock_api, mock_ws):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.side_effect = Exception("TEST ERROR.")

        msg_queue = asyncio.Queue()

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except asyncio.exceptions.TimeoutError:
            pass

        self.assertTrue(self._is_logged("INFO", f"Successfully obtained listen key {self.listen_key}"))
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR.",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    def test_listen_for_user_stream_iter_message_throws_exception(self, mock_api, _, mock_ws):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {"listenKey": self.listen_key}
        mock_api.post(regex_url, body=ujson.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        mock_ws.return_value.closed = False
        mock_ws.return_value.close.side_effect = Exception

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except Exception:
            pass

        self.assertTrue(self._is_logged("INFO", f"Successfully obtained listen key {self.listen_key}"))
        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds... Error: TEST ERROR",
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_successful(self, mock_api, mock_ws):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._simulate_user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        msg = self.async_run_with_timeout(msg_queue.get())
        self.assertTrue(msg, self._simulate_user_update_event)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = utils.rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(self.ev_loop, msg_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())
