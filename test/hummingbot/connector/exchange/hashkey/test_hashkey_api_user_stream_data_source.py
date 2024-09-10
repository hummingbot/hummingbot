import asyncio
import json
import re
import unittest
from typing import Any, Awaitable, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.hashkey import hashkey_constants as CONSTANTS, hashkey_web_utils as web_utils
from hummingbot.connector.exchange.hashkey.hashkey_api_user_stream_data_source import HashkeyAPIUserStreamDataSource
from hummingbot.connector.exchange.hashkey.hashkey_auth import HashkeyAuth
from hummingbot.connector.exchange.hashkey.hashkey_exchange import HashkeyExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class HashkeyUserStreamDataSourceUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "ETH"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = HashkeyAuth(api_key="TEST_API_KEY", secret_key="TEST_SECRET", time_provider=self.mock_time_provider)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = HashkeyExchange(
            client_config_map=client_config_map,
            hashkey_api_key="",
            hashkey_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = HashkeyAPIUserStreamDataSource(
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

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    @aioresponses()
    def test_get_listen_key_log_exception(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, status=400, body=json.dumps(self._error_response()))

        with self.assertRaises(IOError):
            self.async_run_with_timeout(self.data_source._get_listen_key())

    @aioresponses()
    def test_get_listen_key_successful(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        result: str = self.async_run_with_timeout(self.data_source._get_listen_key())

        self.assertEqual(self.listen_key, result)

    @aioresponses()
    def test_ping_listen_key_log_exception(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.put(regex_url, status=400, body=json.dumps(self._error_response()))

        self.data_source._current_listen_key = self.listen_key
        result: bool = self.async_run_with_timeout(self.data_source._ping_listen_key())

        self.assertTrue(self._is_logged("WARNING", f"Failed to refresh the listen key {self.listen_key}: "
                                                   f"{self._error_response()}"))
        self.assertFalse(result)

    @aioresponses()
    def test_ping_listen_key_successful(self, mock_api):
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        mock_api.put(regex_url, body=json.dumps({}))

        self.data_source._current_listen_key = self.listen_key
        result: bool = self.async_run_with_timeout(self.data_source._ping_listen_key())
        self.assertTrue(result)

    @patch("hummingbot.connector.exchange.hashkey.hashkey_api_user_stream_data_source.HashkeyAPIUserStreamDataSource"
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

    @patch("hummingbot.connector.exchange.hashkey.hashkey_api_user_stream_data_source.HashkeyAPIUserStreamDataSource."
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
    def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_api, mock_ws):
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

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
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

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
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
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

        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_pong_payload(self, mock_api, mock_ws):
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        mock_pong = {
            "pong": "1545910590801"
        }
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(mock_pong))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(1, msg_queue.qsize())

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_does_not_queue_ticket_info(self, mock_api, mock_ws):
        url = web_utils.rest_url(path_url=CONSTANTS.USER_STREAM_PATH_URL, domain=self.domain)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_response = {
            "listenKey": self.listen_key
        }
        mock_api.post(regex_url, body=json.dumps(mock_response))

        ticket_info = [
            {
                "e": "ticketInfo",                # Event type
                "E": "1668693440976",             # Event time
                "s": "BTCUSDT",                   # Symbol
                "q": "0.001639",                  # quantity
                "t": "1668693440899",             # time
                "p": "61000.0",                    # price
                "T": "899062000267837441",        # ticketId
                "o": "899048013515737344",        # orderId
                "c": "1621910874883",             # clientOrderId
                "O": "899062000118679808",        # matchOrderId
                "a": "10086",                     # accountId
                "A": 0,                           # ignore
                "m": True,                        # isMaker
                "S": "BUY",                       # side  SELL or BUY
            }
        ]
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(ticket_info))

        msg_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(1, msg_queue.qsize())
