import asyncio
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

import ujson
from aioresponses.core import aioresponses

import hummingbot.connector.derivative.binance_perpetual.binance_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.binance_perpetual import binance_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_auth import BinancePerpetualAuth
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_derivative import BinancePerpetualDerivative
from hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_data_source import (
    BinancePerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BinancePerpetualUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.TESTNET_DOMAIN

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.listen_key = "TEST_LISTEN_KEY"

    async def asyncSetUp(self) -> None:
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.emulated_time = 1640001112.223
        self.connector = BinancePerpetualDerivative(
            binance_perpetual_api_key="",
            binance_perpetual_api_secret="",
            domain=self.domain,
            trading_pairs=[])

        self.auth = BinancePerpetualAuth(api_key=self.api_key,
                                         api_secret=self.secret_key,
                                         time_provider=self)
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        api_factory = web_utils.build_api_factory(auth=self.auth)
        self.data_source = BinancePerpetualUserStreamDataSource(
            auth=self.auth, domain=self.domain, api_factory=api_factory, connector=self.connector,
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

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

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

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    @aioresponses()
    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_data_source.BinancePerpetualUserStreamDataSource._sleep")
    async def test_get_listen_key_exception_raised(self, mock_api, _):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, body=ujson.dumps(self._error_response()))

        with self.assertRaises(IOError):
            await self.data_source._get_listen_key()

    @aioresponses()
    async def test_get_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        result: str = await self.data_source._get_listen_key()

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    async def test_ping_listen_key_failed_log_warning(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, status=400, body=ujson.dumps(self._error_response()))

        self.data_source._current_listen_key = self.listen_key
        result: bool = await self.data_source._ping_listen_key()

        self.assertTrue(
            self._is_logged("WARNING", f"Failed to refresh the listen key {self.listen_key}: {self._error_response()}")
        )
        self.assertFalse(result)

    @aioresponses()
    async def test_ping_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, body=ujson.dumps({}))

        self.data_source._current_listen_key = self.listen_key
        result: bool = await self.data_source._ping_listen_key()
        self.assertTrue(result)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_create_websocket_connection_log_exception(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.side_effect = lambda *arg, **kwars: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch(
        "hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_data_source.BinancePerpetualUserStreamDataSource"
        "._ping_listen_key",
        new_callable=AsyncMock)
    async def test_manage_listen_key_task_loop_keep_alive_failed(self, mock_ping_listen_key):
        mock_ping_listen_key.side_effect = (lambda *args, **kwargs:
                                            self._create_return_value_and_unlock_test_with_event(False))

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.local_event_loop.create_task(self.data_source._manage_listen_key_task_loop())

        await self.resume_test_event.wait()

        # When ping fails, the exception is raised but the _current_listen_key is not reset
        # This is expected since the listen key management task will be restarted by the error handling
        self.assertEqual(None, self.data_source._current_listen_key)

    @aioresponses()
    async def test_manage_listen_key_task_loop_keep_alive_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, body=ujson.dumps({}), callback=self._mock_responses_done_callback)

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.local_event_loop.create_task(self.data_source._manage_listen_key_task_loop())

        await self.mock_done_event.wait()

        self.assertTrue(self._is_logged("INFO", f"Successfully refreshed listen key {self.listen_key}"))
        self.assertGreater(self.data_source._last_listen_key_ping_ts, 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_successful(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._simulate_user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        msg = await msg_queue.get()
        self.assertTrue(msg, self._simulate_user_update_event)
        mock_ws.return_value.ping.assert_called()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_ENDPOINT, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=self._successful_get_listen_key_response())

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    async def test_ensure_listen_key_task_running_with_no_task(self):
        # Test when there's no existing task
        self.assertIsNone(self.data_source._manage_listen_key_task)
        await self.data_source._ensure_listen_key_task_running()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)

    @patch("hummingbot.connector.derivative.binance_perpetual.binance_perpetual_user_stream_data_source.safe_ensure_future")
    async def test_ensure_listen_key_task_running_with_running_task(self, mock_safe_ensure_future):
        # Test when task is already running - should return early (line 155)
        from unittest.mock import MagicMock
        mock_task = MagicMock()
        mock_task.done.return_value = False
        self.data_source._manage_listen_key_task = mock_task

        # Call the method
        await self.data_source._ensure_listen_key_task_running()

        # Should return early without creating a new task
        mock_safe_ensure_future.assert_not_called()
        self.assertEqual(mock_task, self.data_source._manage_listen_key_task)

    async def test_ensure_listen_key_task_running_with_done_task_cancelled_error(self):
        mock_task = AsyncMock()
        mock_task.done.return_value = True
        mock_task.side_effect = asyncio.CancelledError()
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source._ensure_listen_key_task_running()

        # Task should be cancelled and replaced
        mock_task.cancel.assert_called_once()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)
        self.assertNotEqual(mock_task, self.data_source._manage_listen_key_task)

    async def test_ensure_listen_key_task_running_with_done_task_exception(self):
        mock_task = AsyncMock()
        mock_task.done.return_value = True
        mock_task.side_effect = Exception("Test exception")
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source._ensure_listen_key_task_running()

        # Task should be cancelled and replaced, exception should be ignored
        mock_task.cancel.assert_called_once()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)
        self.assertNotEqual(mock_task, self.data_source._manage_listen_key_task)
