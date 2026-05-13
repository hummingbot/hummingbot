import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses

from hummingbot.connector.derivative.architect_perpetual import (
    architect_perpetual_constants as CONSTANTS,
    architect_perpetual_web_utils as web_utils,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_auth import ArchitectPerpetualAuth
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_derivative import (
    ArchitectPerpetualDerivative,
)
from hummingbot.connector.derivative.architect_perpetual.architect_perpetual_user_stream_data_source import (
    ArchitectPerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class ArchitecturePerpetualUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = CONSTANTS.SANDBOX_DOMAIN

        cls.api_key = "test-key"
        cls.secret_key = "test-secret"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.emulated_time = 1640001112.223
        self.connector = ArchitectPerpetualDerivative(
            api_key="",
            api_secret="",
            domain=self.domain,
            trading_pairs=[],
        )

        self.auth = ArchitectPerpetualAuth(
            api_key=self.api_key,
            api_secret=self.secret_key,
            time_provider=self,
            domain=self.domain,
        )
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)
        api_factory = web_utils.build_api_factory(auth=self.auth, domain=self.domain)
        self.data_source = ArchitectPerpetualUserStreamDataSource(
            auth=self.auth, domain=self.domain, api_factory=api_factory, connector=self.connector,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    async def asyncSetUp(self) -> None:
        self.mocking_assistant = NetworkMockingAssistant()

        self.mock_done_event = asyncio.Event()
        self.resume_test_event = asyncio.Event()

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def raise_exception(self, exception_class):
        raise exception_class

    def mock_responses_done_callback(self, *_, **__):
        self.mock_done_event.set()

    def create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def time(self):
        # Implemented to emulate a TimeSynchronizer
        return self.emulated_time

    @staticmethod
    def setup_auth_token(mock_api: aioresponses) -> str:
        expected_token = "test-token"
        url = web_utils.public_rest_url(CONSTANTS.AUTH_TOKEN_ENDPOINT, domain=CONSTANTS.SANDBOX_DOMAIN)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        mock_api.post(regex_url, body=json.dumps({"token": expected_token}))
        return expected_token

    def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_authenticates_and_subscribes_to_events(
        self, mock_api: aioresponses, ws_connect_mock: AsyncMock
    ):
        expected_token = self.setup_auth_token(mock_api=mock_api)
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        messages = asyncio.Queue()
        url = web_utils.private_ws_url(self.domain)
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps({
                "t": "h",
                "ts": 1609459200,
                "tn": 123456789
            }),
        )

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(messages)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value, timeout=1)

        self.assertTrue(
            self.is_logged("INFO", f"Subscribed to private order channels {url}...")
        )
        mock_calls = ws_connect_mock.mock_calls
        self.assertTrue(
            any(
                [
                    mock_call.kwargs.get("headers", {}).get("Authorization", None) == f"Bearer {expected_token}"
                    for mock_call in mock_calls
                ]
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_logs_error(self, mock_api: aioresponses, ws_connect_mock: AsyncMock):
        self.setup_auth_token(mock_api=mock_api)
        messages = asyncio.Queue()
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_exception(
            websocket_mock=ws_connect_mock.return_value, exception=IOError("test error")
        )

        self.listening_task = asyncio.get_event_loop().create_task(
            self.data_source.listen_for_user_stream(messages)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(
            self.is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."
            )
        )

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listening_process_canceled_on_cancel_exception(self, mock_api: aioresponses, ws_connect_mock):
        self.setup_auth_token(mock_api=mock_api)
        messages = asyncio.Queue()
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(self.data_source.listen_for_user_stream(messages), timeout=1)
