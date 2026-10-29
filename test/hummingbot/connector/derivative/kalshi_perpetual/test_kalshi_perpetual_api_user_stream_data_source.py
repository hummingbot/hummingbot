import asyncio
import base64
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_constants as CONSTANTS
import hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_web_utils as web_utils
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_api_user_stream_data_source import (
    KalshiPerpetualAPIUserStreamDataSource,
)
from hummingbot.connector.derivative.kalshi_perpetual.kalshi_perpetual_auth import KalshiPerpetualAuth
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.web_assistant.ws_assistant import WSAssistant


class KalshiPerpetualAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = "test-key-id"
        cls.rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        # Generated at runtime: a committed PEM would trip the detect-private-key pre-commit hook.
        cls.private_key_pem = cls.rsa_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

    async def asyncSetUp(self) -> None:
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.time_provider = MagicMock()
        self.time_provider.time.return_value = 1703123456.789
        self.auth = KalshiPerpetualAuth(
            api_key=self.api_key, private_key=self.private_key_pem, time_provider=self.time_provider)
        self.data_source = KalshiPerpetualAPIUserStreamDataSource(
            auth=self.auth, api_factory=web_utils.build_api_factory(auth=self.auth))

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    # Fixtures shaped after the AsyncAPI spec (per-contract prices and counts)

    def _fill_event(self) -> Dict[str, Any]:
        return {
            "type": "fill", "sid": 1,
            "msg": {"trade_id": "d91bc706-ee49-470d-82d8-11418bda6fed",
                    "order_id": "ee587a1c-8b87-4dcf-b721-9f6f790619fa", "client_order_id": "HBOT-1",
                    "market_ticker": "KXBTCPERP", "is_taker": True, "side": "bid", "ts_ms": 1789038107000,
                    "price": "7.7825", "count": "3.00", "fee_cost": "0.0028", "post_position": "3.00",
                    "order_source": "user"},
        }

    def _user_order_event(self) -> Dict[str, Any]:
        return {
            "type": "user_order", "sid": 2,
            "msg": {"order_id": "ee587a1c-8b87-4dcf-b721-9f6f790619fa",
                    "user_id": "0c3e7a4d-6b1f-4c34-9f86-2d3c8a7a9b10", "client_order_id": "HBOT-1",
                    "ticker": "KXBTCPERP", "side": "bid", "price": "7.7825", "fill_count": "3.00",
                    "remaining_count": "0.00", "created_ts_ms": 1789038106000,
                    "last_updated_ts_ms": 1789038107000, "order_source": "user"},
        }

    def _subscribed_events(self):
        return [{"id": 1, "type": "subscribed", "msg": {"channel": channel, "sid": sid}}
                for sid, channel in enumerate(["fill", "user_orders"], start=1)]

    def test_last_recv_time(self):
        self.assertEqual(0, self.data_source.last_recv_time)

        ws_assistant = MagicMock()
        ws_assistant.last_recv_time = 1000
        self.data_source._ws_assistant = ws_assistant

        self.assertEqual(1000, self.data_source.last_recv_time)

    async def test_get_ws_assistant(self):
        self.assertIsInstance(await self.data_source._get_ws_assistant(), WSAssistant)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_successful_with_user_update_event(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        for event in [*self._subscribed_events(), self._fill_event(), self._user_order_event()]:
            self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(event))
        msg_queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        # Only the order and fill events are queued, raw
        self.assertEqual(2, msg_queue.qsize())
        self.assertEqual(self._fill_event(), msg_queue.get_nowait())
        self.assertEqual(self._user_order_event(), msg_queue.get_nowait())

        # Signed handshake on the margin WS URL, no listen key
        self.assertEqual(CONSTANTS.WSS_URLS[CONSTANTS.DEFAULT_DOMAIN], ws_connect_mock.call_args.args[0])
        self.assertEqual(CONSTANTS.HEARTBEAT_TIME_INTERVAL, ws_connect_mock.call_args.kwargs["heartbeat"])
        headers = ws_connect_mock.call_args.kwargs["headers"]
        self.assertEqual(self.api_key, headers["KALSHI-ACCESS-KEY"])
        self.rsa_key.public_key().verify(
            base64.b64decode(headers["KALSHI-ACCESS-SIGNATURE"]),
            b"1703123456789GET/trade-api/ws/v2/margin",
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(ws_connect_mock.return_value)
        self.assertEqual(
            [{"id": 1, "cmd": "subscribe", "params": {"channels": ["fill", "user_orders"]}}], sent_messages)
        self.assertTrue(self._is_logged("INFO", "Subscribed to private fill and user order channels..."))
        ws_connect_mock.return_value.ping.assert_called()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, "")
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, "{}")
        msg_queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_reconnects_after_an_error_message(self, ws_connect_mock):
        # A rejected subscription keeps the connection open without private events
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        error_event = {"id": 1, "type": "error", "msg": {"code": 9, "msg": "Authentication required"}}
        self.mocking_assistant.add_websocket_aiohttp_message(ws_connect_mock.return_value, json.dumps(error_event))
        self.data_source._sleep = AsyncMock(side_effect=asyncio.CancelledError)  # the pause before reconnecting
        msg_queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(msg_queue)

        self.assertEqual(0, msg_queue.qsize())
        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
        self.assertIsNone(self.data_source._ws_assistant)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_connection_failed(self, sleep_mock, ws_connect_mock):
        ws_connect_mock.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_iter_message_throws_exception(self, ws_connect_mock):
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        ws_connect_mock.return_value.receive.side_effect = [Exception("TEST ERROR"), asyncio.CancelledError]
        self.data_source._sleep = AsyncMock()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
        # The failed connection was dropped and a new one opened
        self.assertEqual(2, ws_connect_mock.call_count)
        self.assertIsNone(self.data_source._ws_assistant)

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(self._is_logged("ERROR", "Unexpected error occurred subscribing to private channels..."))

    async def test_on_user_stream_interruption_disconnects(self):
        ws_assistant = AsyncMock()

        await self.data_source._on_user_stream_interruption(websocket_assistant=ws_assistant)

        ws_assistant.disconnect.assert_awaited_once()
