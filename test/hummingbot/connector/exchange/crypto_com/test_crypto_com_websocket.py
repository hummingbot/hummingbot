import asyncio
import json
import unittest

from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.crypto_com.crypto_com_auth import CryptoComAuth
from hummingbot.connector.exchange.crypto_com.crypto_com_websocket import CryptoComWebsocket
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class CryptoComWebSocketUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pairs = ["COINALPHA-HBOT"]

        cls.api_key = "someKey"
        cls.secret_key = "someSecretKey"
        cls.auth = CryptoComAuth(api_key=cls.api_key, secret_key=cls.secret_key)

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []

        self.websocket = CryptoComWebsocket(auth=self.auth)
        self.websocket.logger().setLevel(1)
        self.websocket.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.async_task: Optional[asyncio.Task] = None

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.ev_loop.run_until_complete(self.websocket.disconnect())
        self.async_task and self.async_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def resume_test_callback(self):
        self.resume_test_event.set()

    async def _iter_message(self):
        async for _ in self.websocket.iter_messages():
            self.resume_test_callback()
            self.async_task.cancel()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_connect_raises_exception(self, _, ws_connect_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR")

        self.websocket = CryptoComWebsocket()

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.websocket.connect())

        self.assertTrue(self._is_logged("ERROR", "Websocket error: 'TEST ERROR'"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_connect_authenticate_is_called(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.async_run_with_timeout(self.websocket.connect())

        sent_payloads = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(1, len(sent_payloads))
        self.assertEqual(CryptoComWebsocket.AUTH_REQUEST, sent_payloads[0]["method"])

    def test_disconnect(self):
        ws = AsyncMock()
        self.websocket._websocket = ws

        self.async_run_with_timeout(self.websocket.disconnect())

        self.assertEqual(1, ws.close.await_count)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_iter_messages_handle_ping(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.async_run_with_timeout(self.websocket.connect())

        mock_ping = {"id": 1587523073344, "method": "public/heartbeat", "code": 0}
        expected_pong_payload = {'id': 1587523073344, 'method': 'public/respond-heartbeat'}
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(mock_ping))

        self.async_task = self.ev_loop.create_task(self._iter_message())

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_payloads = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(2, len(sent_payloads))
        self.assertEqual(expected_pong_payload, sent_payloads[-1])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_subscribe_to_order_book_streams_raises_cancelled_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.websocket.connect())

        ws_connect_mock.return_value.send_json.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.websocket.subscribe_to_order_book_streams(self.trading_pairs))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_subscribe_to_order_book_streams_logs_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.websocket.connect())

        ws_connect_mock.return_value.send_json.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.websocket.subscribe_to_order_book_streams(self.trading_pairs))

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error occurred subscribing to order book trading and delta streams..."
        ))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_subscribe_to_user_streams_raises_cancelled_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.websocket.connect())

        ws_connect_mock.return_value.send_json.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.websocket.subscribe_to_user_streams())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.crypto_com.crypto_com_websocket.CryptoComWebsocket._sleep")
    def test_subscribe_to_user_streams_logs_exception(self, _, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.websocket.connect())

        ws_connect_mock.return_value.send_json.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.websocket.subscribe_to_user_streams())

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error occurred subscribing to user streams..."
        ))
