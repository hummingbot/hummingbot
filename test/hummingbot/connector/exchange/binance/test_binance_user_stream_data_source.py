import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.connector.exchange.binance import binance_constants as CONSTANTS, binance_web_utils as web_utils
from hummingbot.connector.exchange.binance.binance_api_user_stream_data_source import BinanceAPIUserStreamDataSource
from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BinanceUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

        cls.listen_key = "TEST_LISTEN_KEY"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = BinanceAuth(api_key="TEST_API_KEY", secret_key="TEST_SECRET", time_provider=self.mock_time_provider)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        self.connector = BinanceExchange(
            binance_api_key="",
            binance_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = BinanceAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

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
        return json.dumps(resp)

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    @aioresponses()
    @patch("hummingbot.connector.exchange.binance.binance_api_user_stream_data_source.BinanceAPIUserStreamDataSource._sleep")
    async def test_get_listen_key_log_exception(self, mock_api, _):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, body=json.dumps(self._error_response()))

        with self.assertRaises(IOError):
            await self.data_source._get_listen_key()

    @aioresponses()
    async def test_get_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        result: str = await self.data_source._get_listen_key()

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    async def test_ping_listen_key_log_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, status=400, body=json.dumps(self._error_response()))

        self.data_source._current_listen_key = self.listen_key
        result: bool = await self.data_source._ping_listen_key()

        self.assertTrue(self._is_logged("WARNING", f"Failed to refresh the listen key {self.listen_key}: "
                                                   f"{self._error_response()}"))
        self.assertFalse(result)

    @aioresponses()
    async def test_ping_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.put(regex_url, body=json.dumps({}))

        self.data_source._current_listen_key = self.listen_key
        result: bool = await self.data_source._ping_listen_key()
        self.assertTrue(result)

    @patch("hummingbot.connector.exchange.binance.binance_api_user_stream_data_source.BinanceAPIUserStreamDataSource"
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

        self.assertTrue(self._is_logged("ERROR", "Error occurred renewing listen key ... No active exception to reraise"))
        self.assertIsNone(self.data_source._current_listen_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

    @patch("hummingbot.connector.exchange.binance.binance_api_user_stream_data_source.BinanceAPIUserStreamDataSource."
           "_ping_listen_key",
           new_callable=AsyncMock)
    async def test_manage_listen_key_task_loop_keep_alive_successful(self, mock_ping_listen_key):
        mock_ping_listen_key.side_effect = (lambda *args, **kwargs:
                                            self._create_return_value_and_unlock_test_with_event(True))

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._current_listen_key = self.listen_key
        self.data_source._listen_key_initialized_event.set()
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.local_event_loop.create_task(self.data_source._manage_listen_key_task_loop())

        await self.resume_test_event.wait()

        self.assertTrue(self._is_logged("INFO", f"Successfully refreshed listen key {self.listen_key}"))
        self.assertGreater(self.data_source._last_listen_key_ping_ts, 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_get_listen_key_successful_with_user_update_event(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._user_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = await msg_queue.get()
        self.assertEqual(json.loads(self._user_update_event()), msg)
        mock_ws.return_value.ping.assert_called()

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_connection_failed(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

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

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_iter_message_throws_exception(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.BINANCE_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = (lambda *args, **kwargs:
                                                    self._create_exception_and_unlock_test_with_event(
                                                        Exception("TEST ERROR")))
        mock_ws.close.return_value = None

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    async def test_ensure_listen_key_task_running_with_no_task(self):
        # Test when there's no existing task
        self.assertIsNone(self.data_source._manage_listen_key_task)
        await self.data_source._ensure_listen_key_task_running()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)

    @patch("hummingbot.connector.exchange.binance.binance_api_user_stream_data_source.safe_ensure_future")
    async def test_ensure_listen_key_task_running_with_running_task(self, mock_safe_ensure_future):
        # Test when task is already running - should return early (line 164)
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
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.side_effect = asyncio.CancelledError()
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source._ensure_listen_key_task_running()

        # Task should be cancelled and replaced
        mock_task.cancel.assert_called_once()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)
        self.assertNotEqual(mock_task, self.data_source._manage_listen_key_task)

    async def test_ensure_listen_key_task_running_with_done_task_exception(self):
        mock_task = MagicMock()
        mock_task.done.return_value = True
        mock_task.side_effect = Exception("Test exception")
        self.data_source._manage_listen_key_task = mock_task

        await self.data_source._ensure_listen_key_task_running()

        # Task should be cancelled and replaced, exception should be ignored
        mock_task.cancel.assert_called_once()
        self.assertIsNotNone(self.data_source._manage_listen_key_task)
        self.assertNotEqual(mock_task, self.data_source._manage_listen_key_task)
