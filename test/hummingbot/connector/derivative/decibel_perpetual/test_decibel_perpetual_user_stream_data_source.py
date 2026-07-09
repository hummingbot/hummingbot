import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from hummingbot.connector.derivative.decibel_perpetual import decibel_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_auth import DecibelPerpetualAuth
from hummingbot.connector.derivative.decibel_perpetual.decibel_perpetual_user_stream_data_source import (
    DecibelPerpetualUserStreamDataSource,
)
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler
from hummingbot.core.web_assistant.connections.rest_connection import RESTConnection
from hummingbot.core.web_assistant.connections.ws_connection import WSConnection
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class DecibelPerpetualUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    def setUp(self):
        super().setUp()
        self.log_records = []
        self.async_tasks = []

        self.connector = MagicMock()
        self.connector.api_key = "test_api_key"

        self.auth = MagicMock(spec=DecibelPerpetualAuth)
        self.auth.main_wallet_address = "0xmainwallet123"

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.async_tasks = []

        self.client_session = aiohttp.ClientSession(loop=self.local_event_loop)
        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.rest_connection = RESTConnection(self.client_session)
        self.ws_connection = WSConnection(self.client_session)
        self.ws_assistant = WSAssistant(connection=self.ws_connection)

        self.api_factory = MagicMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)

        self.data_source = DecibelPerpetualUserStreamDataSource(
            connector=self.connector,
            api_factory=self.api_factory,
            auth=self.auth,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.mocking_assistant = NetworkMockingAssistant()
        await self.mocking_assistant.async_init()

    def tearDown(self):
        self.run_async_with_timeout(self.client_session.close())
        for task in self.async_tasks:
            task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str):
        return any(record.levelname == log_level and message in record.getMessage() for record in self.log_records)

    async def test_get_account_address(self):
        address = await self.data_source._get_account_address()
        self.assertEqual("0xmainwallet123", address)
        self.assertEqual("0xmainwallet123", self.data_source._subaccount_address)

    async def test_get_account_address_cached(self):
        self.data_source._subaccount_address = "0xcached"
        address = await self.data_source._get_account_address()
        self.assertEqual("0xcached", address)

    async def test_subscribe_channels(self):
        mock_ws = AsyncMock()

        await self.data_source._subscribe_channels(mock_ws)

        self.assertEqual(4, mock_ws.send.call_count)

        for call in mock_ws.send.call_args_list:
            request = call[0][0]
            payload = request.payload
            self.assertEqual("subscribe", payload["method"])
            self.assertIn(":", payload["topic"])
            self.assertIn("0xmainwallet123", payload["topic"])

    async def test_subscribe_channels_contains_all_private_channels(self):
        mock_ws = AsyncMock()

        await self.data_source._subscribe_channels(mock_ws)

        topics = []
        for call in mock_ws.send.call_args_list:
            topics.append(call[0][0].payload["topic"])

        self.assertTrue(any(CONSTANTS.WS_ACCOUNT_OVERVIEW_CHANNEL in t for t in topics))
        self.assertTrue(any(CONSTANTS.WS_USER_POSITIONS_CHANNEL in t for t in topics))
        self.assertTrue(any(CONSTANTS.WS_USER_OPEN_ORDERS_CHANNEL in t for t in topics))
        self.assertTrue(any(CONSTANTS.WS_USER_TRADES_CHANNEL in t for t in topics))

    async def test_subscribe_channels_cancelled_error(self):
        mock_ws = AsyncMock()
        mock_ws.send.side_effect = asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_on_user_stream_interruption_cancels_ping(self):
        """Test that _on_user_stream_interruption cancels the ping task."""
        mock_ws = AsyncMock()

        # Create a task that will be running
        cancel_event = asyncio.Event()

        async def long_running():
            try:
                await cancel_event.wait()
            except asyncio.CancelledError:
                raise

        ping_task = asyncio.create_task(long_running())
        self.data_source._ping_task = ping_task

        await self.data_source._on_user_stream_interruption(mock_ws)

        # Allow task to process
        await asyncio.sleep(0)

        self.assertIsNone(self.data_source._ping_task)
        # Cancel the sleep event cleanly
        cancel_event.set()
        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass

    async def test_connected_websocket_assistant(self):
        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=mock_ws)

        await self.data_source._connected_websocket_assistant()

        mock_ws.connect.assert_called_once()
        call_kwargs = mock_ws.connect.call_args.kwargs
        self.assertIn("ws_headers", call_kwargs)
        self.assertEqual("Bearer test_api_key", call_kwargs["ws_headers"]["Authorization"])

    async def test_connected_websocket_assistant_no_api_key(self):
        self.connector.api_key = None

        mock_ws = AsyncMock()
        mock_ws.connect = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=mock_ws)

        await self.data_source._connected_websocket_assistant()

        call_kwargs = mock_ws.connect.call_args.kwargs
        ws_headers = call_kwargs.get("ws_headers", {})
        self.assertNotIn("Authorization", ws_headers)
