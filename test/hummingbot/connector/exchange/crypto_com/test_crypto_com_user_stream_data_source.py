import asyncio
import aiohttp
import ujson
import unittest

from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange.crypto_com.crypto_com_api_user_stream_data_source import (
    CryptoComAPIUserStreamDataSource,
)
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class CryptoComAPIUserStreamDataSourceUnitTests(unittest.TestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()

        cls.api_key = "someKey"
        cls.secret_key = "someSecretKey"
        cls.auth = CryptoComAuth(api_key=cls.api_key, secret_key=cls.secret_key)

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.async_task: Optional[asyncio.Task] = None

        self.data_source = CryptoComAPIUserStreamDataSource(crypto_com_auth=self.auth)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.resume_test_event = asyncio.Event()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_get_shared_client_not_shared_client_provided(self):
        self.assertIsNone(self.data_source._shared_client)
        self.assertIsInstance(self.data_source._get_shared_client(), aiohttp.ClientSession)

    def test_get_shared_client_shared_client_provided(self):
        aiohttp_client = aiohttp.ClientSession()
        data_source = CryptoComAPIUserStreamDataSource(crypto_com_auth=self.auth, shared_client=aiohttp_client)
        self.assertEqual(data_source._get_shared_client(), aiohttp_client)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_raised_cancelled(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_logs_exception(self, ws_connect_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.data_source._create_websocket_connection())

        self.assertTrue(self._is_logged(
            "NETWORK", "Unexpected error occured connecting to crypto_com WebSocket API. (TEST ERROR)"
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_user_stream_raises_cancelled_exception(self, _, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.data_source.listen_for_user_stream(asyncio.Queue()))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_user_stream_raises_logs_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = lambda: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR")
        )
        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(asyncio.Queue()))

        self.async_run_with_timeout(self.resume_test_event.wait())

        self.assertTrue(
            self._is_logged(
                "ERROR", "Unexpected error when listening to user streams. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_listen_for_user_stream_successful(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        auth_response = {
            "id": 1,
            "method": "public/auth",
            "code": 0
        }

        balance_response = {
            "method": "subscribe",
            "result": {
                "subscription": "user.balance",
                "channel": "user.balance",
                "data": [
                    {
                        "currency": "COINALPHA",
                        "balance": 1,
                        "available": 1,
                        "order": 0,
                        "stake": 0
                    }
                ],
                "channel": "user.balance"
            }
        }

        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(auth_response))
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, ujson.dumps(balance_response))

        user_stream_queue = asyncio.Queue()
        self.async_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(user_stream_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(self.data_source.ready)
        self.assertEqual(1, user_stream_queue.qsize())
