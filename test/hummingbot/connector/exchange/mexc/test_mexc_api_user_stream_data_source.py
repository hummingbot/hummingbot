import asyncio
from collections import Awaitable
from unittest import TestCase
from unittest.mock import patch, AsyncMock

import ujson

from hummingbot.connector.exchange.mexc.mexc_api_user_stream_data_source import MexcAPIUserStreamDataSource
from hummingbot.connector.exchange.mexc.mexc_auth import MexcAuth
import hummingbot.connector.exchange.mexc.mexc_constants as CONSTANTS
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from test.hummingbot.connector.network_mocking_assistant import NetworkMockingAssistant


class MexcAPIUserStreamDataSourceTests(TestCase):
    # the level is required to receive logs from the data source loger
    level = 0

    def setUp(self) -> None:
        super().setUp()
        self.uid = '001'
        self.api_key = 'testAPIKey'
        self.secret = 'testSecret'
        self.account_id = 528
        self.username = 'hbot'
        self.oms_id = 1
        self.log_records = []
        self.listening_task = None
        self.ev_loop = asyncio.get_event_loop()

        throttler = AsyncThrottler(CONSTANTS.RATE_LIMITS)
        auth_assistant = MexcAuth(api_key=self.api_key,
                                  secret_key=self.secret)
        self.data_source = MexcAPIUserStreamDataSource(throttler, auth_assistant)
        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_authenticates_and_subscribes_to_events(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                    messages))
        # Add a dummy message for the websocket to read and include in the "messages" queue
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value,
                                                             ujson.dumps({'channel': 'push.personal.order'}))

        first_received_message = self.async_run_with_timeout(messages.get())
        self.assertEqual({'channel': 'push.personal.order'}, first_received_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listening_process_canceled_when_cancel_exception_during_initialization(self, ws_connect_mock):
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            self.listening_task = asyncio.get_event_loop().create_task(
                self.data_source.listen_for_user_stream(asyncio.get_event_loop(),
                                                        messages))
            self.async_run_with_timeout(self.listening_task)
