import asyncio
import json
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

from hummingbot.connector.exchange.binance import binance_constants as CONSTANTS
from hummingbot.connector.exchange.binance.binance_api_user_stream_data_source import BinanceAPIUserStreamDataSource
from hummingbot.connector.exchange.binance.binance_auth import BinanceAuth
from hummingbot.connector.exchange.binance.binance_exchange import BinanceExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.api_throttler.async_throttler import AsyncThrottler


class BinanceUserStreamDataSourceUnitTests(IsolatedAsyncioWrapperTestCase):
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = "COINALPHA"
        cls.quote_asset = "HBOT"
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = cls.base_asset + cls.quote_asset
        cls.domain = "com"

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.throttler = AsyncThrottler(rate_limits=CONSTANTS.RATE_LIMITS)
        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000
        self.auth = BinanceAuth(api_key="TEST_API_KEY", secret_key="TEST_SECRET", time_provider=self.mock_time_provider)
        self.time_synchronizer = TimeSynchronizer()
        self.time_synchronizer.add_time_offset_ms_sample(0)

        self.connector = BinanceExchange(
            binance_api_key="",
            binance_api_secret="",
            trading_pairs=[],
            trading_required=False,
            domain=self.domain)
        self.connector._web_assistants_factory._auth = self.auth

        self.data_source = BinanceAPIUserStreamDataSource(
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

    def _error_response(self) -> Dict[str, Any]:
        return {
            "code": "ERROR CODE",
            "msg": "ERROR MESSAGE"
        }

    def _user_update_event(self):
        # WS API wraps events in {"subscriptionId": N, "event": {...}}
        resp = {
            "subscriptionId": 0,
            "event": {
                "e": "balanceUpdate",
                "E": 1573200697110,
                "a": "BTC",
                "d": "100.00000000",
                "T": 1573200697068
            }
        }
        return json.dumps(resp)

    def _user_update_event_inner(self):
        return {
            "e": "balanceUpdate",
            "E": 1573200697110,
            "a": "BTC",
            "d": "100.00000000",
            "T": 1573200697068
        }

    def _ws_subscribe_success_response(self, request_id: str = "test-id"):
        return json.dumps({
            "id": request_id,
            "status": 200,
            "result": {}
        })

    def _ws_subscribe_error_response(self, request_id: str = "test-id"):
        return json.dumps({
            "id": request_id,
            "status": 400,
            "error": {
                "code": -1022,
                "msg": "Signature for this request is not valid."
            }
        })

    # --- Auth signing tests ---

    def test_generate_ws_signature(self):
        params = {"apiKey": "TEST_API_KEY", "timestamp": 1000000}
        signature = self.auth.generate_ws_signature(params)
        # Verify deterministic output
        self.assertIsInstance(signature, str)
        self.assertEqual(len(signature), 64)  # SHA-256 hex digest
        # Verify same input produces same output
        self.assertEqual(signature, self.auth.generate_ws_signature(params))

    def test_generate_ws_signature_alphabetical_sorting(self):
        # Ensure params are sorted alphabetically regardless of input order
        params_a = {"timestamp": 1000000, "apiKey": "TEST_API_KEY"}
        params_b = {"apiKey": "TEST_API_KEY", "timestamp": 1000000}
        self.assertEqual(
            self.auth.generate_ws_signature(params_a),
            self.auth.generate_ws_signature(params_b),
        )

    def test_generate_ws_subscribe_params(self):
        params = self.auth.generate_ws_subscribe_params()
        self.assertEqual(params["apiKey"], "TEST_API_KEY")
        self.assertIn("timestamp", params)
        self.assertIn("signature", params)
        self.assertEqual(len(params["signature"]), 64)

    # --- Subscribe channel tests ---

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_successful(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._connected_websocket_assistant()
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._ws_subscribe_success_response()
        )

        await self.data_source._subscribe_channels(ws)
        self.assertTrue(
            self._is_logged("INFO", "Successfully subscribed to user data stream via WebSocket API")
        )

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_subscribe_channels_failure(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()

        ws = await self.data_source._connected_websocket_assistant()
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._ws_subscribe_error_response()
        )

        with self.assertRaises(IOError):
            await self.data_source._subscribe_channels(ws)

    # --- Process event message tests ---

    async def test_process_event_message_filters_api_responses(self):
        queue = asyncio.Queue()
        # API response messages (with id + status) should be filtered out
        api_response = {"id": "some-uuid", "status": 200, "result": {}}
        await self.data_source._process_event_message(api_response, queue)
        self.assertEqual(0, queue.qsize())

    async def test_process_event_message_queues_user_events(self):
        queue = asyncio.Queue()
        user_event = {
            "e": "balanceUpdate",
            "E": 1573200697110,
            "a": "BTC",
            "d": "100.00000000",
            "T": 1573200697068,
        }
        await self.data_source._process_event_message(user_event, queue)
        self.assertEqual(1, queue.qsize())
        self.assertEqual(user_event, queue.get_nowait())

    async def test_process_event_message_unwraps_ws_api_event_container(self):
        queue = asyncio.Queue()
        inner_event = {
            "e": "executionReport",
            "E": 1499405658658,
            "s": "ETHBTC",
            "x": "NEW",
            "X": "NEW",
            "i": 4293153,
        }
        wrapped_event = {"subscriptionId": 0, "event": inner_event}
        await self.data_source._process_event_message(wrapped_event, queue)
        self.assertEqual(1, queue.qsize())
        self.assertEqual(inner_event, queue.get_nowait())

    async def test_process_event_message_handles_stream_terminated(self):
        queue = asyncio.Queue()
        terminated_event = {
            "subscriptionId": 0,
            "event": {
                "e": "eventStreamTerminated",
                "E": 1728973001334
            }
        }
        with self.assertRaises(ConnectionError):
            await self.data_source._process_event_message(terminated_event, queue)
        self.assertEqual(0, queue.qsize())

    async def test_process_event_message_does_not_queue_empty_payload(self):
        queue = asyncio.Queue()
        await self.data_source._process_event_message({}, queue)
        self.assertEqual(0, queue.qsize())

    # --- Integration tests ---

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_subscribe_and_receive_event(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        # First message: subscribe success response
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._ws_subscribe_success_response()
        )
        # Second message: actual user data event
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._user_update_event()
        )

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        msg = await msg_queue.get()
        # Events are unwrapped from the WS API container before being queued
        self.assertEqual(self._user_update_event_inner(), msg)
        mock_ws.return_value.ping.assert_called()

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_empty_payload(self, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        # Subscribe success
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._ws_subscribe_success_response()
        )
        # Empty payload
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, "")

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)
        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_connection_failed(self, mock_ws):
        mock_ws.side_effect = lambda *arg, **kwars: self._create_exception_and_unlock_test_with_event(
            Exception("TEST ERROR."))

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_iter_message_throws_exception(self, mock_ws):
        msg_queue: asyncio.Queue = asyncio.Queue()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        # Subscribe success first
        self.mocking_assistant.add_websocket_aiohttp_message(
            mock_ws.return_value, self._ws_subscribe_success_response()
        )
        # Then receive throws
        mock_ws.return_value.receive.side_effect = (lambda *args, **kwargs:
                                                    self._create_exception_and_unlock_test_with_event(
                                                        Exception("TEST ERROR")))
        mock_ws.close.return_value = None

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_user_stream(msg_queue)
        )

        await self.resume_test_event.wait()

        self.assertTrue(
            self._is_logged(
                "ERROR",
                "Unexpected error while listening to user stream. Retrying after 5 seconds..."))
