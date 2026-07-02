import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source import GeminiAPIUserStreamDataSource
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class GeminiUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "BTC"
        cls.quote_asset = "USD"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = "btcusd"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant()

        self.connector = GeminiExchange(
            gemini_api_key="TEST_API_KEY",
            gemini_api_secret="TEST_SECRET",
            trading_pairs=[self.trading_pair],
            trading_required=False)

        self.data_source = GeminiAPIUserStreamDataSource(
            auth=self.connector.authenticator,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_connected_websocket_assistant_sends_auth_headers(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws = await self.data_source._connected_websocket_assistant()
        self.assertIsNotNone(ws)
        ws_connect_mock.assert_called_once()
        _, kwargs = ws_connect_mock.call_args
        self.assertIn("X-GEMINI-APIKEY", kwargs["headers"])
        self.assertTrue(self._is_logged("INFO", "Successfully connected to authenticated user stream"))

    async def test_subscribe_channels_sends_order_and_balance_requests(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        await self.data_source._subscribe_channels(mock_ws)
        self.assertEqual(2, mock_ws.send.await_count)
        self.assertTrue(self._is_logged(
            "INFO", "Subscribed to user order events and balance update channels..."))

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock(side_effect=Exception("Test Error"))
        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)
        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error occurred subscribing to user stream channels..."))

    async def test_on_user_stream_interruption_disconnects(self):
        mock_ws = MagicMock()
        mock_ws.disconnect = AsyncMock()
        await self.data_source._on_user_stream_interruption(mock_ws)
        mock_ws.disconnect.assert_awaited_once()
        self.assertTrue(self._is_logged("INFO", "User stream interrupted. Cleaning up..."))

    async def test_on_user_stream_interruption_handles_none(self):
        await self.data_source._on_user_stream_interruption(None)
        self.assertTrue(self._is_logged("INFO", "User stream interrupted. Cleaning up..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channel_constants(self, ws_connect_mock):
        mock_ws = MagicMock()
        mock_ws.send = AsyncMock()
        await self.data_source._subscribe_channels(mock_ws)
        sent_payloads = [call.args[0].payload for call in mock_ws.send.await_args_list]
        self.assertEqual([CONSTANTS.WS_ORDER_EVENTS_STREAM], sent_payloads[0]["params"])
        self.assertEqual([CONSTANTS.WS_BALANCE_STREAM], sent_payloads[1]["params"])
