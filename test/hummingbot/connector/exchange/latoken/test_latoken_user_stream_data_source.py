import asyncio
import json
import re
import unittest
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.latoken import (  # latoken_utils as utils
    latoken_constants as CONSTANTS,
    latoken_web_utils as web_utils,
)
from hummingbot.connector.exchange.latoken.latoken_api_user_stream_data_source import LatokenAPIUserStreamDataSource
from hummingbot.connector.exchange.latoken.latoken_auth import LatokenAuth
from hummingbot.connector.exchange.latoken.latoken_exchange import LatokenExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class LatokenUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "d8ae67f2-f954-4014-98c8-64b1ac334c64"
        cls.quote_asset = "0c3a106d-bde3-4c13-a26e-3fd2394529e5"
        cls.trading_pair = "ETH-USDT"
        cls.trading_pairs = [cls.trading_pair]
        cls.ex_trading_pair = cls.base_asset + '/' + cls.quote_asset
        cls.domain = "com"

        cls.listen_key = 'ffffffff-ffff-ffff-ffff-ffffffffff'

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = LatokenAuth(api_key="TEST_API_KEY", secret_key="TEST_SECRET", time_provider=self.mock_time_provider)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = LatokenExchange(
            client_config_map=client_config_map,
            latoken_api_key="",
            latoken_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = LatokenAPIUserStreamDataSource(
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

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _error_response(self) -> Dict[str, Any]:
        resp = {
            "code": "ERROR CODE",
            "msg": "ERROR MESSAGE"
        }

        return resp

    def _user_update_event(self):
        # Balance Update, so not the initial balance
        return b'MESSAGE\ndestination:/user/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx/v1/account\nmessage-id:9e8188c8-682c-41cd-9a14-722bf6dfd99e\ncontent-length:346\nsubscription:2\n\n{"payload":[{"id":"44d36460-46dc-4828-a17c-63b1a047b054","status":"ACCOUNT_STATUS_ACTIVE","type":"ACCOUNT_TYPE_SPOT","timestamp":1650120265819,"currency":"620f2019-33c0-423b-8a9d-cde4d7f8ef7f","available":"34.001000000000000000","blocked":"0.999000000000000000","user":"2d2a5729-e9e3-4f8b-9e3a-f1c5e147099f"}],"nonce":1,"timestamp":1650120265830}\x00'

    def _successfully_subscribed_event(self):
        return b'CONNECTED\nserver:vertx-stomp/3.9.6\nheart-beat:1000,1000\nsession:37a8e962-7fa7-4eab-b163-146eeafdef63\nversion:1.1\n\n\x00 '

    @aioresponses()
    def test_get_listen_key_log_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=json.dumps(self._error_response()))

        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source._get_listen_key())

    @aioresponses()
    def test_get_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {'id': 'ffffffff-ffff-ffff-ffff-ffffffffff', 'status': 'ACTIVE', 'role': 'INVESTOR',
                         'email': 'ed.rouwendaal@latoken.com', 'phone': '', 'authorities': [],
                         'forceChangePassword': None, 'authType': 'API_KEY', 'socials': []}

        mock_api.get(regex_url, body=json.dumps(mock_response))

        result: str = self.async_run_with_timeout(self.data_source._get_listen_key())

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    def test_ping_listen_key_log_exception(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.get(regex_url, status=400, body=json.dumps(self._error_response()))

        self.data_source._current_listen_key = self.listen_key
        result: bool = self.async_run_with_timeout(self.data_source._ping_listen_key())

        self.assertTrue(
            self._is_logged("WARNING", f"Failed to refresh the listen key {self.listen_key}: {self._error_response()}"))
        self.assertFalse(result)

    @aioresponses()
    def test_ping_listen_key_successful(self, mock_api):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_response = {'id': 'ffffffff-ffff-ffff-ffff-ffffffffff', 'status': 'ACTIVE', 'role': 'INVESTOR',
                         'email': 'ed.rouwendaal@latoken.com', 'phone': '', 'authorities': [],
                         'forceChangePassword': None, 'authType': 'API_KEY', 'socials': []}

        mock_api.get(regex_url, body=json.dumps(mock_response))

        self.data_source._current_listen_key = self.listen_key
        result: bool = self.async_run_with_timeout(self.data_source._ping_listen_key())
        self.assertTrue(result)

    @patch("hummingbot.connector.exchange.latoken.latoken_api_user_stream_data_source.LatokenAPIUserStreamDataSource"
           "._ping_listen_key",
           new_callable=AsyncMock)
    def test_manage_listen_key_task_loop_keep_alive_failed(self, mock_ping_listen_key):
        mock_ping_listen_key.side_effect = (lambda *args, **kwargs:
                                            self._create_return_value_and_unlock_test_with_event(False))

        self.data_source._current_listen_key = self.listen_key

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.ev_loop.create_task(self.data_source._manage_listen_key_task_loop())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("ERROR", "Error occurred renewing listen key ..."))
        self.assertIsNone(self.data_source._current_listen_key)
        self.assertFalse(self.data_source._listen_key_initialized_event.is_set())

    @patch("hummingbot.connector.exchange.latoken.latoken_api_user_stream_data_source.LatokenAPIUserStreamDataSource."
           "_ping_listen_key",
           new_callable=AsyncMock)
    def test_manage_listen_key_task_loop_keep_alive_successful(self, mock_ping_listen_key):
        mock_ping_listen_key.side_effect = (lambda *args, **kwargs:
                                            self._create_return_value_and_unlock_test_with_event(True))

        # Simulate LISTEN_KEY_KEEP_ALIVE_INTERVAL reached
        self.data_source._current_listen_key = self.listen_key
        self.data_source._listen_key_initialized_event.set()
        self.data_source._last_listen_key_ping_ts = 0

        self.listening_task = self.ev_loop.create_task(self.data_source._manage_listen_key_task_loop())

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(self._is_logged("INFO", f"Refreshed listen key {self.listen_key}."))
        self.assertGreater(self.data_source._last_listen_key_ping_ts, 0)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_get_listen_key_successful_with_user_update_event(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {'id': 'ffffffff-ffff-ffff-ffff-ffffffffff', 'status': 'ACTIVE', 'role': 'INVESTOR',
                         'email': 'ed.rouwendaal@latoken.com', 'phone': '', 'authorities': [],
                         'forceChangePassword': None, 'authType': 'API_KEY', 'socials': []}

        mock_api.get(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._successfully_subscribed_event(), message_type=aiohttp.WSMsgType.BINARY)
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._user_update_event(), message_type=aiohttp.WSMsgType.BINARY)

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = self.async_run_with_timeout(msg_queue.get())
        self.assertTrue(msg, self._user_update_event)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {'id': 'ffffffff-ffff-ffff-ffff-ffffffffff', 'status': 'ACTIVE', 'role': 'INVESTOR',
                         'email': 'ed.rouwendaal@latoken.com', 'phone': '', 'authorities': [],
                         'forceChangePassword': None, 'authType': 'API_KEY', 'socials': []}
        mock_api.get(regex_url, body=json.dumps(mock_response))

        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_connection_failed(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {'id': 'ffffffff-ffff-ffff-ffff-ffffffffff', 'status': 'ACTIVE', 'role': 'INVESTOR',
                         'email': 'ed.rouwendaal@latoken.com', 'phone': '', 'authorities': [],
                         'forceChangePassword': None, 'authType': 'API_KEY', 'socials': []}
        mock_api.get(regex_url, body=json.dumps(mock_response))

        mock_ws.side_effect = lambda *arg, **kwars: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_iter_message_throws_exception(self, mock_api, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.USER_ID_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {'id': 'ffffffff-ffff-ffff-ffff-ffffffffff', 'status': 'ACTIVE', 'role': 'INVESTOR',
                         'email': 'ed.rouwendaal@latoken.com', 'phone': '', 'authorities': [],
                         'forceChangePassword': None, 'authType': 'API_KEY', 'socials': []}
        mock_api.get(regex_url, body=json.dumps(mock_response))

        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = (lambda *args, **kwargs:
                                                    self._create_exception_and_unlock_test_with_event(
                                                        Exception("TEST ERROR")))
        mock_ws.close.return_value = None

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
