import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.mexc import mexc_constants as CONSTANTS, mexc_web_utils as web_utils
from hummingbot.connector.exchange.mexc.mexc_api_user_stream_data_source import MexcAPIUserStreamDataSource
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
from hummingbot.connector.exchange.mexc.mexc_exchange import MexcExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class MexcUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
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
        self.auth = MexcAuth(api_key="TEST_API_KEY", secret_key="TEST_SECRET", time_provider=self.mock_time_provider)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = MexcExchange(
            client_config_map=client_config_map,
            mexc_api_key="",
            mexc_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = MexcAPIUserStreamDataSource(
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
            "c": "spot@private.account.v3.api",
            "d": {
                "a": "BTC",
                "c": 1678185928428,
                "f": "302.185113007893322435",
                "fd": "-4.990689704",
                "l": "4.990689704",
                "ld": "4.990689704",
                "o": "ENTRUST_PLACE"
            },
            "t": 1678185928435
        }
        return json.dumps(resp)

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    @aioresponses()
    async def test_get_listen_key_log_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, body=json.dumps(self._error_response()))

        with self.assertRaises(IOError):
            await self.data_source._get_listen_key()

    @aioresponses()
    async def test_get_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        result: str = await self.data_source._get_listen_key()

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    async def test_ping_listen_key_log_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, status=400, body=json.dumps(self._error_response()))

        self.data_source._current_listen_key = self.listen_key
        result: bool = await self.data_source._ping_listen_key()

        self.assertTrue(self._is_logged("WARNING", f"Failed to refresh the listen key {self.listen_key}: "
                                                   f"{self._error_response()}"))
        self.assertFalse(result)

    @aioresponses()
    async def test_ping_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.put(regex_url, body=json.dumps({}))

        self.data_source._current_listen_key = self.listen_key
        result: bool = await self.data_source._ping_listen_key()
        self.assertTrue(result)

    @patch("hummingbot.connector.exchange.mexc.mexc_api_user_stream_data_source.MexcAPIUserStreamDataSource"
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

        self.assertTrue(self._is_logged("ERROR", "Error occurred renewing listen key ..."))
        self.assertIsNone(self.data_source._current_listen_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

    @patch("hummingbot.connector.exchange.mexc.mexc_api_user_stream_data_source.MexcAPIUserStreamDataSource."
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

        self.assertTrue(self._is_logged("INFO", f"Refreshed listen key {self.listen_key}."))
        self.assertGreater(self.data_source._last_listen_key_ping_ts, 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_get_listen_key_successful_with_user_update_event(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._user_update_event())
        self.data_source._sleep = AsyncMock()
        self.data_source._sleep.side_effect = asyncio.CancelledError()
        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = await msg_queue.get()
        self.assertEqual(json.loads(self._user_update_event()), msg)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        self.data_source._sleep = AsyncMock()
        self.data_source._sleep.side_effect = asyncio.CancelledError()
        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_connection_failed(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
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
        url = web_utils.private_rest_url(path_url=CONSTANTS.MEXC_USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))
        self.data_source._sleep = AsyncMock()
        self.data_source._sleep.side_effect = asyncio.CancelledError()
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        mock_ws.close.return_value = None

        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
