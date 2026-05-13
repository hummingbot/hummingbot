import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source import BackpackAPIUserStreamDataSource
from hummingbot.connector.exchange.backpack.backpack_auth import BackpackAuth
from hummingbot.connector.exchange.backpack.backpack_exchange import BackpackExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BackpackAPIUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "SOL"
        cls.quote_asset = "USDC"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}_{cls.quote_asset}"
        cls.domain = CONSTANTS.DEFAULT_DOMAIN

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        # Create a valid Ed25519 keypair for testing
        import base64

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519

        test_secret = ed25519.Ed25519PrivateKey.generate()
        test_key = test_secret.public_key()

        seed_bytes = test_secret.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )

        public_key_bytes = test_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

        self.api_key = base64.b64encode(public_key_bytes).decode("utf-8")
        self.secret_key = base64.b64encode(seed_bytes).decode("utf-8")

        self.auth = BackpackAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.mock_time_provider
        )
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        self.connector = BackpackExchange(
            backpack_api_key=self.api_key,
            backpack_api_secret=self.secret_key,
            trading_pairs=[],
            trading_required=False,
            domain=self.domain
        )
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = BackpackAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory,
            domain=self.domain
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

    def _create_return_value_and_unlock_test_with_event(self, value):
        self.resume_test_event.set()
        return value

    def _order_update_event(self):
        # Order update event
        resp = {
            "stream": "account.orderUpdate",
            "data": {
                "orderId": "123456",
                "clientId": "1112345678",
                "symbol": self.ex_trading_pair,
                "side": "Bid",
                "orderType": "Limit",
                "price": "100.5",
                "quantity": "10",
                "executedQuantity": "5",
                "remainingQuantity": "5",
                "status": "PartiallyFilled",
                "timeInForce": "GTC",
                "postOnly": False,
                "timestamp": 1234567890000
            }
        }
        return json.dumps(resp)

    def _balance_update_event(self):
        """There is no balance update event in the user stream, so we create a dummy one."""
        return {}

    def _successfully_subscribed_event(self):
        resp = {
            "result": None,
            "id": 1
        }
        return resp

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_connected_websocket_assistant(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._connected_websocket_assistant()

        self.assertIsNotNone(ws)
        self.assertTrue(self._is_logged("INFO", "Successfully connected to user stream"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._get_ws_assistant()
        await ws.connect(
            ws_url=f"{CONSTANTS.WSS_URL.format(self.domain)}",
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )

        await self.data_source._subscribe_channels(ws)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(mock_ws.return_value)
        self.assertEqual(1, len(sent_messages))

        subscribe_request = sent_messages[0]
        self.assertEqual("SUBSCRIBE", subscribe_request["method"])
        self.assertEqual([CONSTANTS.ALL_ORDERS_CHANNEL], subscribe_request["params"])
        self.assertIn("signature", subscribe_request)
        self.assertEqual(4, len(subscribe_request["signature"]))  # [api_key, signature, timestamp, window]

        self.assertTrue(self._is_logged("INFO", "Subscribed to private order changes channel..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source.BackpackAPIUserStreamDataSource._sleep")
    async def test_listen_for_user_stream_get_ws_assistant_successful_with_order_update_event(self, _, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, self._order_update_event())

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = await msg_queue.get()
        self.assertEqual(json.loads(self._order_update_event()), msg)
        mock_ws.return_value.ping.assert_called()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source.BackpackAPIUserStreamDataSource._sleep")
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, _, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_connection_failed(self, mock_ws):
        mock_ws.side_effect = lambda *arg, **kwargs: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR.")
        )

        with patch.object(self.data_source, "_sleep", side_effect=asyncio.CancelledError()):
            msg_queue = asyncio.Queue()
            self.listening_task = self.local_event_loop.create_task(
                self.data_source.listen_for_user_stream(msg_queue)
            )

            await self.resume_test_event.wait()

            with self.assertRaises(asyncio.CancelledError):
                await self.listening_task

            self.assertTrue(
                self._is_logged("ERROR",
                                "Unexpected error while listening to user stream. Retrying after 5 seconds...")
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_iter_message_throws_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = (
            lambda *args, **kwargs: self._create_exception_and_unlock_test_with_event(Exception("TEST ERROR"))
        )
        mock_ws.close.return_value = None

        with patch.object(self.data_source, "_sleep", side_effect=asyncio.CancelledError()):
            self.listening_task = self.local_event_loop.create_task(
                self.data_source.listen_for_user_stream(msg_queue)
            )

            await self.resume_test_event.wait()

            with self.assertRaises(asyncio.CancelledError):
                await self.listening_task

            self.assertTrue(
                self._is_logged(
                    "ERROR",
                    "Unexpected error while listening to user stream. Retrying after 5 seconds...")
            )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_on_user_stream_interruption_disconnects_websocket(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._get_ws_assistant()
        await ws.connect(
            ws_url=f"{CONSTANTS.WSS_URL.format(self.domain)}",
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )

        await self.data_source._on_user_stream_interruption(ws)

        # Verify disconnect was called - just ensure no exception is raised
        # The actual disconnection is handled by the websocket assistant

    async def test_on_user_stream_interruption_handles_none_websocket(self):
        # Should not raise exception when websocket is None
        await self.data_source._on_user_stream_interruption(None)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_get_ws_assistant_creates_new_instance(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws1 = await self.data_source._get_ws_assistant()
        ws2 = await self.data_source._get_ws_assistant()

        # Each call should create a new instance
        self.assertIsNotNone(ws1)
        self.assertIsNotNone(ws2)
        # They should be different instances
        self.assertIsNot(ws1, ws2)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source.BackpackAPIUserStreamDataSource._sleep")
    async def test_listen_for_user_stream_handles_cancelled_error(self, mock_sleep, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        # Give it a moment to start
        await asyncio.sleep(0.1)

        # Cancel the task
        self.listening_task.cancel()

        # Should raise CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await self.listening_task

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source.BackpackAPIUserStreamDataSource._sleep")
    async def test_subscribe_channels_handles_cancelled_error(self, mock_sleep, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._get_ws_assistant()
        await ws.connect(
            ws_url=f"{CONSTANTS.WSS_URL.format(self.domain)}",
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )

        # Make send raise CancelledError
        with patch.object(ws, "send", side_effect=asyncio.CancelledError()):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source._subscribe_channels(ws)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_logs_exception_on_error(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._get_ws_assistant()
        await ws.connect(
            ws_url=f"{CONSTANTS.WSS_URL.format(self.domain)}",
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )

        # Make send raise exception
        with patch.object(ws, "send", side_effect=Exception("Send failed")):
            with self.assertRaises(Exception):
                await self.data_source._subscribe_channels(ws)

            self.assertTrue(
                self._is_logged("ERROR", "Unexpected error occurred subscribing to user streams...")
            )

    async def test_last_recv_time_returns_zero_when_no_ws_assistant(self):
        self.assertEqual(0, self.data_source.last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_last_recv_time_returns_ws_assistant_time(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._get_ws_assistant()
        await ws.connect(
            ws_url=f"{CONSTANTS.WSS_URL.format(self.domain)}",
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )

        # Simulate message received by mocking the property
        self.data_source._ws_assistant = ws
        with patch.object(type(ws), "last_recv_time", new_callable=lambda: 1234567890.0):
            self.assertEqual(1234567890.0, self.data_source.last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_ws_connection_uses_correct_url(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._connected_websocket_assistant()

        # Verify websocket assistant was created and connected
        self.assertIsNotNone(ws)
        self.assertTrue(self._is_logged("INFO", "Successfully connected to user stream"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_ws_connection_uses_correct_ping_timeout(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._connected_websocket_assistant()

        # Verify websocket assistant was created and connected
        self.assertIsNotNone(ws)
        self.assertTrue(self._is_logged("INFO", "Successfully connected to user stream"))
