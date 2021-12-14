import asyncio
import unittest

from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
from hummingbot.connector.exchange.mexc.mexc_websocket_adaptor import MexcWebSocketAdaptor
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
import hummingbot.connector.exchange.mexc.mexc_constants as CONSTANTS


class MexcWebSocketUnitTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.trading_pairs = ["COINALPHA-HBOT"]

        cls.api_key = "someKey"
        cls.secret_key = "someSecretKey"
        cls.auth = MexcAuth(api_key=cls.api_key, secret_key=cls.secret_key)

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)

        self.websocket = MexcWebSocketAdaptor(throttler)
        self.websocket.logger().setLevel(1)
        self.websocket.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        self.async_task: Optional[asyncio.Task] = None

        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.async_run_with_timeout(self.websocket.disconnect())
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
    def test_connect_raises_exception(self, ws_connect_mock):
        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        ws_connect_mock.side_effect = Exception("TEST ERROR")

        self.websocket = MexcWebSocketAdaptor(throttler)

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.websocket.connect())

        self.assertTrue(self._is_logged("ERROR", "Websocket error: 'TEST ERROR'"))

    def test_disconnect(self):
        ws = AsyncMock()
        self.websocket._websocket = ws

        self.async_run_with_timeout(self.websocket.disconnect())

        self.assertEqual(1, ws.close.await_count)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_to_order_book_streams_raises_cancelled_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.websocket.connect())

        ws_connect_mock.return_value.send_str.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.async_run_with_timeout(self.websocket.subscribe_to_order_book_streams(self.trading_pairs))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_subscribe_to_order_book_streams_logs_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.async_run_with_timeout(self.websocket.connect())

        ws_connect_mock.return_value.send_str.side_effect = Exception("TEST ERROR")

        with self.assertRaisesRegex(Exception, "TEST ERROR"):
            self.async_run_with_timeout(self.websocket.subscribe_to_order_book_streams(self.trading_pairs))

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error occurred subscribing to order book trading and delta streams..."
        ))
