import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source import GeminiAPIUserStreamDataSource
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant


class _UserStreamAckWS:
    def __init__(self, acks):
        self.acks = list(acks)
        self.sent_payloads = []

    async def send(self, request):
        self.sent_payloads.append(request.payload)

    async def iter_messages(self):
        if self.acks:
            yield MagicMock(data=self.acks.pop(0))


class _HangingUserStreamAckWS(_UserStreamAckWS):
    async def iter_messages(self):
        await asyncio.Event().wait()
        if False:
            yield None


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

    def _queue_subscription_success_acks(self, websocket_mock):
        # listen_for_user_stream first awaits the "user_orders" and "user_balances" subscription
        # acks (non-matching frames are consumed and dropped), so these MUST precede any event.
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=websocket_mock,
            message=json.dumps({"id": "user_orders", "status": 200, "result": {}}))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=websocket_mock,
            message=json.dumps({"id": "user_balances", "status": 200, "result": {}}))

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
        mock_ws = _UserStreamAckWS([
            {"id": "user_orders", "status": 200, "result": {}},
            {"id": "user_balances", "status": 200, "result": {}},
        ])
        await self.data_source._subscribe_channels(mock_ws)
        self.assertEqual(2, len(mock_ws.sent_payloads))
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

    async def test_subscribe_channels_raises_on_error_ack(self):
        mock_ws = _UserStreamAckWS([
            {"id": "user_orders", "status": 401, "error": {"msg": "auth failed"}},
        ])

        with self.assertRaises(IOError):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertEqual(1, len(mock_ws.sent_payloads))
        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error occurred subscribing to user stream channels..."))

    async def test_subscribe_channels_raises_on_ack_timeout(self):
        mock_ws = _HangingUserStreamAckWS([])

        with patch.object(CONSTANTS, "WS_SUBSCRIPTION_REQUEST_TIMEOUT", 0.01):
            with self.assertRaises(IOError):
                await self.data_source._subscribe_channels(mock_ws)

        self.assertEqual(1, len(mock_ws.sent_payloads))

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
        mock_ws = _UserStreamAckWS([
            {"id": "user_orders", "status": 200, "result": {}},
            {"id": "user_balances", "status": 200, "result": {}},
        ])
        await self.data_source._subscribe_channels(mock_ws)
        sent_payloads = mock_ws.sent_payloads
        self.assertEqual([CONSTANTS.WS_ORDER_EVENTS_STREAM], sent_payloads[0]["params"])
        self.assertEqual([CONSTANTS.WS_BALANCE_STREAM], sent_payloads[1]["params"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_queues_order_event(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self._queue_subscription_success_acks(ws_connect_mock.return_value)

        order_event = {
            "e": "executionReport",
            "E": 1700000000000000000,
            "s": "btcusd",
            "i": 123456789,
            "c": "HBOTBUY123",
            "S": "BUY",
            "o": "LIMIT",
            "X": "NEW",
            "p": "10.00",
            "q": "1.0",
            "z": "0",
            "T": 1700000000000000000,
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(order_event))

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, msg_queue.qsize())
        self.assertEqual(order_event, msg_queue.get_nowait())
        self.assertTrue(self._is_logged(
            "INFO", "Subscribed to user order events and balance update channels..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_queues_balance_event(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self._queue_subscription_success_acks(ws_connect_mock.return_value)

        balance_event = {
            "e": "balanceUpdate",
            "E": 1700000000000,
            "B": [{"a": "USD", "f": "207.39", "c": "300.00"}],
        }
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(balance_event))

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(1, msg_queue.qsize())
        self.assertEqual(balance_event, msg_queue.get_nowait())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self._queue_subscription_success_acks(ws_connect_mock.return_value)

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps({}))

        msg_queue: asyncio.Queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_logs_warning_on_connection_error(self, ws_connect_mock):
        ws_connect_mock.side_effect = [ConnectionError("test"), asyncio.CancelledError]

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        self.assertTrue(self._is_logged("WARNING", "The websocket connection was closed (test)"))
        self.assertTrue(self._is_logged("INFO", "User stream interrupted. Cleaning up..."))

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_logs_exception_and_retries(self, ws_connect_mock, sleep_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError

        try:
            await self.data_source.listen_for_user_stream(asyncio.Queue())
        except asyncio.CancelledError:
            pass

        self.assertTrue(self._is_logged(
            "ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
        sleep_mock.assert_called_once_with(1.0)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_raises_cancel_exception_during_connect(self, ws_connect_mock):
        ws_connect_mock.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())
