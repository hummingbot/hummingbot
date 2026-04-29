import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.gemini import gemini_constants as CONSTANTS
from hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source import GeminiAPIUserStreamDataSource
from hummingbot.connector.exchange.gemini.gemini_auth import GeminiAuth
from hummingbot.connector.exchange.gemini.gemini_exchange import GeminiExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class GeminiAPIUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset.lower()}{cls.quote_asset.lower()}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.api_key = "test_api_key"
        self.secret_key = "test_secret_key"

        self.auth = GeminiAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.mock_time_provider,
        )
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        self.connector = GeminiExchange(
            gemini_api_key=self.api_key,
            gemini_api_secret=self.secret_key,
            trading_pairs=[],
            trading_required=False,
            domain=self.domain,
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = GeminiAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain,
        )

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def _raise_exception(self, exception_class):
        raise exception_class

    def _create_exception_and_unlock_test_with_event(self, exception):
        self.resume_test_event.set()
        raise exception

    def _order_accepted_event(self):
        resp = {
            "type": "accepted",
            "order_id": "123456",
            "event_id": "ev_1",
            "client_order_id": "client_order_1",
            "symbol": self.ex_trading_pair,
            "side": "buy",
            "order_type": "exchange limit",
            "timestampms": 1640780000000,
            "timestamp": 1640780000,
            "is_live": True,
            "is_cancelled": False,
            "original_amount": "1.0",
            "price": "50000.00",
            "executed_amount": "0",
            "remaining_amount": "1.0",
        }
        return json.dumps(resp)

    def _heartbeat_event(self):
        return json.dumps({
            "type": "heartbeat",
            "timestampms": 1640780000000,
        })

    def _subscription_ack_event(self):
        return json.dumps({
            "type": "subscription_ack",
            "accountId": 12345,
            "subscriptionId": "ws-order-events-123",
        })

    def _fill_event(self):
        resp = {
            "type": "fill",
            "order_id": "123456",
            "event_id": "ev_2",
            "client_order_id": "client_order_1",
            "symbol": self.ex_trading_pair,
            "side": "buy",
            "order_type": "exchange limit",
            "timestampms": 1640780001000,
            "timestamp": 1640780001,
            "is_live": False,
            "is_cancelled": False,
            "original_amount": "1.0",
            "price": "50000.00",
            "executed_amount": "1.0",
            "remaining_amount": "0",
            "fill": {
                "trade_id": "99999",
                "liquidity": "Taker",
                "price": "50000.00",
                "amount": "1.0",
                "fee": "17.50",
                "fee_currency": "USD",
            },
        }
        return json.dumps(resp)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_connected_websocket_assistant(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._connected_websocket_assistant()

        self.assertIsNotNone(ws)
        self.assertTrue(self._is_logged("INFO", "Successfully connected to Gemini order events stream"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_logs_info(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_ORDER_EVENTS_URL,
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )

        await self.data_source._subscribe_channels(ws)

        self.assertTrue(self._is_logged("INFO", "Subscribed to private order events channel..."))

    async def test_process_event_message_filters_heartbeats(self):
        queue = asyncio.Queue()
        heartbeat = {"type": "heartbeat", "timestampms": 123}
        await self.data_source._process_event_message(heartbeat, queue)
        self.assertEqual(0, queue.qsize())

    async def test_process_event_message_filters_subscription_ack(self):
        queue = asyncio.Queue()
        ack = {"type": "subscription_ack", "accountId": 1}
        await self.data_source._process_event_message(ack, queue)
        self.assertEqual(0, queue.qsize())

    async def test_process_event_message_queues_accepted_event(self):
        queue = asyncio.Queue()
        event = {"type": "accepted", "order_id": "123"}
        await self.data_source._process_event_message(event, queue)
        self.assertEqual(1, queue.qsize())
        msg = queue.get_nowait()
        self.assertEqual("accepted", msg["type"])

    async def test_process_event_message_queues_fill_event(self):
        queue = asyncio.Queue()
        event = {"type": "fill", "order_id": "456", "fill": {"trade_id": "789"}}
        await self.data_source._process_event_message(event, queue)
        self.assertEqual(1, queue.qsize())

    async def test_process_event_message_queues_cancelled_event(self):
        queue = asyncio.Queue()
        event = {"type": "cancelled", "order_id": "456"}
        await self.data_source._process_event_message(event, queue)
        self.assertEqual(1, queue.qsize())

    async def test_process_event_message_queues_rejected_event(self):
        queue = asyncio.Queue()
        event = {"type": "rejected", "order_id": "456"}
        await self.data_source._process_event_message(event, queue)
        self.assertEqual(1, queue.qsize())

    async def test_process_event_message_queues_closed_event(self):
        queue = asyncio.Queue()
        event = {"type": "closed", "order_id": "456"}
        await self.data_source._process_event_message(event, queue)
        self.assertEqual(1, queue.qsize())

    async def test_process_event_message_queues_booked_event(self):
        queue = asyncio.Queue()
        event = {"type": "booked", "order_id": "456"}
        await self.data_source._process_event_message(event, queue)
        self.assertEqual(1, queue.qsize())

    async def test_process_event_message_handles_initial_snapshot_list(self):
        queue = asyncio.Queue()
        # Gemini sends initial snapshot as a list of order dicts with type "initial"
        snapshot = [
            {"type": "initial", "order_id": "100"},
            {"type": "initial", "order_id": "101"},
            {"type": "fill", "order_id": "102"},  # fill not in initial/accepted/booked, should be skipped
        ]
        await self.data_source._process_event_message(snapshot, queue)
        # Only initial/accepted/booked from the snapshot should be queued
        self.assertEqual(2, queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source.GeminiAPIUserStreamDataSource._sleep",
           new_callable=AsyncMock)
    async def test_listen_for_user_stream_processes_order_event(self, _, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._order_accepted_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue))

        msg = await msg_queue.get()
        self.assertEqual("accepted", msg["type"])
        self.assertEqual("123456", msg["order_id"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source.GeminiAPIUserStreamDataSource._sleep",
           new_callable=AsyncMock)
    async def test_listen_for_user_stream_filters_heartbeat(self, _, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._heartbeat_event())
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._order_accepted_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue))

        msg = await msg_queue.get()
        # First message should be the accepted event (heartbeat filtered out)
        self.assertEqual("accepted", msg["type"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.gemini.gemini_api_user_stream_data_source.GeminiAPIUserStreamDataSource._sleep",
           new_callable=AsyncMock)
    async def test_listen_for_user_stream_processes_fill_event(self, _, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._fill_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue))

        msg = await msg_queue.get()
        self.assertEqual("fill", msg["type"])
        self.assertIn("fill", msg)
        self.assertEqual("99999", msg["fill"]["trade_id"])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_connection_failed(self, mock_ws):
        mock_ws.side_effect = lambda *arg, **kwargs: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR.")
        )

        with patch.object(self.data_source, "_sleep", side_effect=asyncio.CancelledError()):
            msg_queue = asyncio.Queue()
            self.listening_task = self.local_event_loop.create_task(
                self.data_source.listen_for_user_stream(msg_queue))

            await self.resume_test_event.wait()

            with self.assertRaises(asyncio.CancelledError):
                await self.listening_task

            self.assertTrue(
                self._is_logged("ERROR",
                                "Unexpected error while listening to user stream. Retrying after 5 seconds...")
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_on_user_stream_interruption_disconnects_websocket(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_ORDER_EVENTS_URL,
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL,
        )

        await self.data_source._on_user_stream_interruption(ws)
        # Should not raise

    async def test_on_user_stream_interruption_handles_none_websocket(self):
        await self.data_source._on_user_stream_interruption(None)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_get_ws_assistant_creates_new_instance(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws1 = await self.data_source._get_ws_assistant()
        ws2 = await self.data_source._get_ws_assistant()

        self.assertIsNotNone(ws1)
        self.assertIsNotNone(ws2)
        self.assertIsNot(ws1, ws2)

    def test_generate_ws_auth_headers_present(self):
        headers = self.auth.generate_ws_auth_headers()
        self.assertIn("X-GEMINI-APIKEY", headers)
        self.assertIn("X-GEMINI-PAYLOAD", headers)
        self.assertIn("X-GEMINI-SIGNATURE", headers)
        self.assertEqual(self.api_key, headers["X-GEMINI-APIKEY"])
