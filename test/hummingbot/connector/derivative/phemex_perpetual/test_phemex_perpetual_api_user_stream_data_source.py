import asyncio
import json
import unittest
from typing import Awaitable, Optional
from unittest.mock import AsyncMock, patch

from hummingbot.connector.derivative.phemex_perpetual import (
    phemex_perpetual_constants as CONSTANTS,
    phemex_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_user_stream_data_source import (
    PhemexPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_auth import PhemexPerpetualAuth
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class PhemexPerpetualAPIUserStreamDataSourceTest(unittest.TestCase):
    ev_loop: asyncio.AbstractEventLoop
    base_asset: str
    quote_asset: str
    trading_pair: str
    exchange_trading_pair: str
    domain: str
    api_key: str
    secret_key: str
    listen_key: str

    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.exchange_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

        cls.api_key = "TEST_API_KEY"
        cls.secret_key = "TEST_SECRET_KEY"
        cls.listen_key = "TEST_LISTEN_KEY"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.emulated_time = 1640001112.223

        self.auth = PhemexPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.secret_key,
            time_provider=self,
        )
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        api_factory = web_utils.build_api_factory(auth=self.auth)
        self.data_source = PhemexPerpetualAPIUserStreamDataSource(
            auth=self.auth,
            api_factory=api_factory,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mock_done_event = asyncio.Event()
        self.resume_test_event = asyncio.Event()

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_user_stream_data_source."
        "PhemexPerpetualAPIUserStreamDataSource._sleep"
    )
    def test_create_websocket_connection_log_exception(self, sleep_mock: AsyncMock, ws_mock: AsyncMock):
        ws_mock.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(coroutine=self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.exceptions.CancelledError:
            pass

        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="Unexpected error while listening to user stream. Retrying after 5 seconds...",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_user_stream_data_source."
        "PhemexPerpetualAPIUserStreamDataSource._sleep"
    )
    def test_create_websocket_connection_log_authentication_failure(self, sleep_mock: AsyncMock, ws_mock: AsyncMock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()
        auth_error_message = {
            "error": {"code": 6012, "message": "invalid login token"},
            "id": None,
            "result": None,
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(auth_error_message)
        )

        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            self.async_run_with_timeout(coroutine=self.data_source.listen_for_user_stream(msg_queue))
        except asyncio.exceptions.CancelledError:
            pass

        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="Error authenticating the private websocket connection",
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_create_websocket_connection_authenticates(self, ws_mock: AsyncMock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()
        auth_success_message = {
            "error": None,
            "id": 0,
            "result": {"status": "success"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(auth_success_message)
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(asyncio.Queue()))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            websocket_mock=ws_mock.return_value
        )

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_mock.return_value,
        )

        self.assertLessEqual(1, len(sent_messages))

        auth_message = sent_messages[0]
        expected_auth_message = self.auth.get_ws_auth_payload()

        self.assertEqual(expected_auth_message, auth_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_logs_subscription_errors(self, ws_mock: AsyncMock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()
        auth_success_message = {
            "error": None,
            "id": 0,
            "result": {"status": "success"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(auth_success_message)
        )
        subscription_error_message = {
            "error": {'code': 6001, 'message': 'invalid argument'},
            "id": None,
            "result": None,
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(subscription_error_message)
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(asyncio.Queue()))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            websocket_mock=ws_mock.return_value
        )

        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="Unexpected error occurred subscribing to the private account channel..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_subscribes_to_user_stream(self, ws_mock: AsyncMock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()
        success_message = {
            "error": None,
            "id": 0,
            "result": {"status": "success"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(success_message)  # auth
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(success_message)  # subscription
        )

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(asyncio.Queue()))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            websocket_mock=ws_mock.return_value
        )

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_mock.return_value,
        )

        self.assertEqual(3, len(sent_messages))

        auth_message = sent_messages[1]
        expected_auth_message = {
            "id": 0,
            "method": "aop_p.subscribe",
            "params": [],
        }

        self.assertEqual(expected_auth_message, auth_message)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch(
        "hummingbot.connector.derivative.phemex_perpetual.phemex_perpetual_api_user_stream_data_source."
        "PhemexPerpetualAPIUserStreamDataSource._sleep"
    )
    def test_listen_for_user_stream_iter_message_throws_exception(self, _: AsyncMock, ws_mock: AsyncMock):
        msg_queue: asyncio.Queue = asyncio.Queue()
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_mock.return_value.receive.side_effect = Exception("TEST ERROR")
        ws_mock.return_value.closed = False
        ws_mock.return_value.close.side_effect = Exception

        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))

        try:
            self.async_run_with_timeout(msg_queue.get())
        except Exception:
            pass

        self.assertTrue(
            self.is_logged(
                log_level="ERROR",
                message="Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    def test_listen_for_user_stream_forwards_events(self, ws_mock: AsyncMock):
        ws_mock.return_value = self.mocking_assistant.create_websocket_mock()
        success_message = {
            "error": None,
            "id": 0,
            "result": {"status": "success"},
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(success_message)  # auth
        )
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(success_message)  # subscription
        )
        event_message = {
            "some": "event",
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_mock.return_value, message=json.dumps(event_message)
        )

        message_queue = asyncio.Queue()
        self.listening_task = self.ev_loop.create_task(self.data_source.listen_for_user_stream(message_queue))

        self.mocking_assistant.run_until_all_aiohttp_messages_delivered(
            websocket_mock=ws_mock.return_value
        )

        self.assertFalse(message_queue.empty())

        received_message = message_queue.get_nowait()

        self.assertEqual(event_message, received_message)
