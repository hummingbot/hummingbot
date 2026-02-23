import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

import hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.grvt_perpetual.grvt_perpetual_user_stream_data_source import (
    GrvtPerpetualUserStreamDataSource,
)


class GrvtPerpetualUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        self.log_records = []
        self.listening_task = None

        self.auth = MagicMock()
        self.auth.ensure_session = AsyncMock()
        self.auth.get_ws_auth_headers = MagicMock(
            return_value={"Cookie": "gravity=test_cookie", "X-Grvt-Account-Id": "test_id"}
        )

        self.connector = MagicMock()
        self.api_factory = MagicMock()

        self.data_source = GrvtPerpetualUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        if self.listening_task is not None:
            self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def test_last_recv_time_no_ws(self):
        self.data_source._ws_assistant = None
        self.assertEqual(0, self.data_source.last_recv_time)

    def test_last_recv_time_with_ws(self):
        mock_ws = MagicMock()
        mock_ws.last_recv_time = 12345.0
        self.data_source._ws_assistant = mock_ws
        self.assertEqual(12345.0, self.data_source.last_recv_time)

    async def test_process_event_message_order_channel(self):
        queue = asyncio.Queue()
        event = {"channel": CONSTANTS.WS_ORDER_CHANNEL, "data": {"order_id": "123"}}

        await self.data_source._process_event_message(event, queue)

        self.assertFalse(queue.empty())
        queued_msg = queue.get_nowait()
        self.assertEqual(event, queued_msg)

    async def test_process_event_message_fill_channel(self):
        queue = asyncio.Queue()
        event = {"channel": CONSTANTS.WS_FILL_CHANNEL, "data": {"trade_id": "456"}}

        await self.data_source._process_event_message(event, queue)

        self.assertFalse(queue.empty())
        queued_msg = queue.get_nowait()
        self.assertEqual(event, queued_msg)

    async def test_process_event_message_position_channel(self):
        queue = asyncio.Queue()
        event = {"channel": CONSTANTS.WS_POSITION_CHANNEL, "data": {"instrument": "BTC_USDT_Perp"}}

        await self.data_source._process_event_message(event, queue)

        self.assertFalse(queue.empty())

    async def test_process_event_message_order_state_channel(self):
        queue = asyncio.Queue()
        event = {"channel": CONSTANTS.WS_ORDER_STATE_CHANNEL, "data": {"order_id": "789"}}

        await self.data_source._process_event_message(event, queue)

        self.assertFalse(queue.empty())

    async def test_process_event_message_unknown_channel_ignored(self):
        queue = asyncio.Queue()
        event = {"channel": "unknown_channel", "data": {}}

        await self.data_source._process_event_message(event, queue)

        self.assertTrue(queue.empty())

    async def test_process_event_message_error_raises(self):
        queue = asyncio.Queue()
        event = {"error": {"message": "something went wrong"}}

        with self.assertRaises(IOError):
            await self.data_source._process_event_message(event, queue)

    async def test_process_event_message_error_string(self):
        queue = asyncio.Queue()
        event = {"error": "simple error string"}

        with self.assertRaises(IOError):
            await self.data_source._process_event_message(event, queue)

    async def test_get_ws_assistant_creates_new(self):
        mock_ws = MagicMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=mock_ws)
        self.data_source._ws_assistant = None

        result = await self.data_source._get_ws_assistant()

        self.assertEqual(mock_ws, result)
        self.api_factory.get_ws_assistant.assert_called_once()

    async def test_get_ws_assistant_returns_existing(self):
        existing_ws = MagicMock()
        self.data_source._ws_assistant = existing_ws

        result = await self.data_source._get_ws_assistant()

        self.assertEqual(existing_ws, result)
