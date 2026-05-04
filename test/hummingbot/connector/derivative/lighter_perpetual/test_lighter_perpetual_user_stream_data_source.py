import asyncio
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _ensure_limit_order_stub():
    module_name = "hummingbot.core.data_type.limit_order"
    try:
        __import__(module_name)
        return
    except Exception:
        pass
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class LimitOrder:
        pass

    stub_module.LimitOrder = LimitOrder
    sys.modules[module_name] = stub_module


def _ensure_order_book_stub():
    module_name = "hummingbot.core.data_type.order_book"
    try:
        __import__(module_name)
        return
    except Exception:
        pass
    if module_name in sys.modules:
        return
    stub_module = types.ModuleType(module_name)

    class OrderBook:
        pass

    stub_module.OrderBook = OrderBook
    sys.modules[module_name] = stub_module


class LighterPerpetualUserStreamDataSourceTests(unittest.IsolatedAsyncioTestCase):

    data_source_cls = None
    auth_cls = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_limit_order_stub()
        _ensure_order_book_stub()
        try:
            from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_auth import LighterPerpetualAuth
            from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source import (
                LighterPerpetualUserStreamDataSource,
            )

            cls.data_source_cls = LighterPerpetualUserStreamDataSource
            cls.auth_cls = LighterPerpetualAuth
        except ModuleNotFoundError:
            cls.data_source_cls = None

    def setUp(self):
        super().setUp()
        if self.data_source_cls is None:
            self.skipTest("Compiled hummingbot core modules are unavailable in this environment")

        self.connector = MagicMock()
        self.connector.rest_api_key = "api-key"

        self.auth = self.auth_cls(
            api_key="api-key",
            api_secret="api-secret",
            account_identifier="237600",
        )
        self.auth.user_wallet_public_key = "237600"

        self.ws_assistant = AsyncMock()
        self.api_factory = MagicMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)

        self.data_source = self.data_source_cls(
            connector=self.connector,
            api_factory=self.api_factory,
            auth=self.auth,
        )

    @patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source.safe_ensure_future")
    async def test_connected_websocket_assistant_connects_with_api_key_header(self, safe_future_mock):
        safe_future_mock.side_effect = lambda coro: (coro.close(), MagicMock())[1]
        ws = await self.data_source._connected_websocket_assistant()

        self.assertIs(self.ws_assistant, ws)
        self.ws_assistant.connect.assert_awaited_once()
        connect_kwargs = self.ws_assistant.connect.call_args.kwargs
        self.assertEqual({"X-Api-Key": "api-key"}, connect_kwargs["ws_headers"])
        self.assertEqual(1, safe_future_mock.call_count)

    async def test_subscribe_channels_sends_all_private_subscriptions(self):
        self.ws_assistant.receive = AsyncMock(return_value=SimpleNamespace(data={"type": "connected"}))
        self.connector.account_index = "237600"
        self.connector.api_key_index = "1"
        self.connector._account_index = "237600"  # enables account_all_orders subscription
        self.connector._build_account_auth_params = MagicMock(return_value={"auth": "token-1"})
        self.auth.user_wallet_public_key = "0xabc"

        await self.data_source._subscribe_channels(self.ws_assistant)

        self.ws_assistant.receive.assert_awaited_once()
        # 3 identifiers * 6 channels * 2 delimiters + 2 account_all_orders channels
        self.assertEqual(38, self.ws_assistant.send.await_count)
        sent_payloads = [call.args[0].payload for call in self.ws_assistant.send.await_args_list]
        self.assertIn({"type": "subscribe", "channel": "account_all/0xabc"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "account_all:0xabc"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "account_positions/237600"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "account_positions:237600"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "account_trades/1"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "account_trades:1"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "user_stats/0xabc"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "user_stats:237600"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "account_all_orders:237600", "auth": "token-1"}, sent_payloads)
        self.assertIn({"type": "subscribe", "channel": "account_all_orders/237600", "auth": "token-1"}, sent_payloads)

    async def test_subscribe_channels_raises_when_connected_message_missing(self):
        self.ws_assistant.receive = AsyncMock(return_value=SimpleNamespace(data={"type": "unexpected"}))

        with self.assertRaises(IOError):
            await self.data_source._subscribe_channels(self.ws_assistant)

    async def test_on_user_stream_interruption_cancels_ping_task(self):
        ping_task = MagicMock()
        self.data_source._ping_task = ping_task

        await self.data_source._on_user_stream_interruption(None)

        ping_task.cancel.assert_called_once()
        self.assertIsNone(self.data_source._ping_task)

    async def test_ping_loop_sends_ping_payload(self):
        sent_payloads = []

        async def send_side_effect(request):
            sent_payloads.append(request.payload)
            raise asyncio.CancelledError()

        self.ws_assistant.send.side_effect = send_side_effect

        with patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source.asyncio.sleep", new=AsyncMock()):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source._ping_loop(self.ws_assistant)

        self.assertEqual([{"type": "ping"}], sent_payloads)

    async def test_ping_loop_returns_when_ws_disconnects(self):
        self.ws_assistant.send.side_effect = RuntimeError("WS is not connected")

        with patch("hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source.asyncio.sleep", new=AsyncMock()):
            result = await self.data_source._ping_loop(self.ws_assistant)

        self.assertIsNone(result)

    async def test_subscribe_channels_raises_on_send_error(self):
        self.ws_assistant.receive = AsyncMock(return_value=SimpleNamespace(data={"type": "connected"}))
        self.ws_assistant.send.side_effect = Exception("boom")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(self.ws_assistant)

    async def test_process_websocket_messages_replies_to_ping_and_enqueues_account_all_updates(self):
        ws_messages = [
            SimpleNamespace(data={"type": "ping"}),
            SimpleNamespace(data={"type": "update/account_all", "channel": "account_all:237600", "positions": {}}),
        ]

        async def iter_messages():
            for message in ws_messages:
                yield message

        self.ws_assistant.iter_messages = iter_messages
        output = asyncio.Queue()

        await self.data_source._process_websocket_messages(self.ws_assistant, output)

        self.ws_assistant.send.assert_awaited_once()
        self.assertEqual({"type": "pong"}, self.ws_assistant.send.call_args.args[0].payload)
        queued_event = output.get_nowait()
        self.assertEqual("update/account_all", queued_event["type"])

    async def test_listen_for_user_stream_get_listen_key_successful_with_user_update_event(self):
        output = asyncio.Queue()
        ws = MagicMock()
        ws.disconnect = AsyncMock()
        self.data_source._connected_websocket_assistant = AsyncMock(return_value=ws)
        self.data_source._subscribe_channels = AsyncMock()
        self.data_source._send_ping = AsyncMock()

        async def process_messages(websocket_assistant, queue):
            queue.put_nowait({"type": "update/account_all", "channel": "account_all:237600"})
            raise asyncio.CancelledError()

        self.data_source._process_websocket_messages = process_messages

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(output)

        self.assertEqual("update/account_all", output.get_nowait()["type"])

    async def test_listen_for_user_stream_does_not_queue_empty_payload(self):
        output = asyncio.Queue()
        await self.data_source._process_event_message({}, output)
        self.assertTrue(output.empty())

    async def test_process_event_message_queues_type_only_dedicated_updates(self):
        output = asyncio.Queue()
        event = {"type": "update/account_order_updates", "data": [{"i": 1, "os": "cancelled"}]}

        await self.data_source._process_event_message(event, output)

        self.assertFalse(output.empty())
        queued = output.get_nowait()
        self.assertEqual("update/account_order_updates", queued["type"])

    async def test_process_event_message_ignores_invalid_channel_errors(self):
        output = asyncio.Queue()
        event = {"error": {"code": 30005, "message": "Invalid Channel"}}

        await self.data_source._process_event_message(event, output)

        self.assertTrue(output.empty())

    async def test_process_event_message_raises_non_channel_errors(self):
        output = asyncio.Queue()
        event = {"error": {"code": 30099, "message": "Auth failed"}}

        with self.assertRaises(IOError):
            await self.data_source._process_event_message(event, output)

    async def test_listen_for_user_stream_connection_failed(self):
        self.data_source._connected_websocket_assistant = AsyncMock(side_effect=[ConnectionError("closed"), asyncio.CancelledError()])
        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

    async def test_listen_for_user_stream_iter_message_throws_exception(self):
        ws = MagicMock()
        ws.disconnect = AsyncMock()
        self.data_source._connected_websocket_assistant = AsyncMock(return_value=ws)
        self.data_source._subscribe_channels = AsyncMock()
        self.data_source._send_ping = AsyncMock()
        self.data_source._process_websocket_messages = AsyncMock(side_effect=Exception("boom"))
        self.data_source._sleep = AsyncMock(side_effect=asyncio.CancelledError())

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

    # ── listen_for_user_stream connection-error branches ──────────────────

    async def test_listen_for_user_stream_logs_debug_on_close_code_1000(self):
        """ConnectionError with 'close code = 1000' logs debug (line 55)."""
        logger = MagicMock()
        self.data_source.logger = MagicMock(return_value=logger)
        self.data_source._on_user_stream_interruption = AsyncMock()
        self.data_source._connected_websocket_assistant = AsyncMock(
            side_effect=[ConnectionError("close code = 1000 (normal closure)"), asyncio.CancelledError()]
        )

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_user_stream(asyncio.Queue())

        logger.debug.assert_called()

    async def test_listen_for_user_stream_suppresses_repeated_errors(self):
        """Second rapid Exception within 30 s is suppressed with debug log (line 64)."""
        import time as time_module
        logger = MagicMock()
        self.data_source.logger = MagicMock(return_value=logger)
        self.data_source._on_user_stream_interruption = AsyncMock()
        self.data_source._sleep = AsyncMock(side_effect=[None, asyncio.CancelledError()])
        self.data_source._connected_websocket_assistant = AsyncMock(
            side_effect=[RuntimeError("first"), RuntimeError("second"), asyncio.CancelledError()]
        )

        now_ts = time_module.time()
        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source.time.time",
            side_effect=[now_ts, now_ts + 1.0],  # second error within 30 s → suppressed
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source.listen_for_user_stream(asyncio.Queue())

        logger.debug.assert_called()

    # ── _subscribe_channels auth_params exception path ─────────────────────

    async def test_subscribe_channels_auth_params_exception_ignored(self):
        """Exception in _build_account_auth_params is silently ignored (lines 131-132)."""
        self.ws_assistant.receive = AsyncMock(return_value=SimpleNamespace(data={"type": "connected"}))
        self.connector.account_index = "237600"
        self.connector.api_key_index = "1"
        self.connector._account_index = "237600"
        self.connector._build_account_auth_params = MagicMock(side_effect=RuntimeError("auth-err"))
        self.auth.user_wallet_public_key = "0xabc"

        # Should complete without raising
        await self.data_source._subscribe_channels(self.ws_assistant)
        # Some sends still happened for the general account channels
        self.assertTrue(self.ws_assistant.send.await_count > 0)

    # ── _ping_loop exception branches ─────────────────────────────────────

    async def test_ping_loop_re_raises_runtime_error_for_other_messages(self):
        """RuntimeError NOT matching 'WS is not connected' is re-raised (line 215)."""
        self.ws_assistant.send.side_effect = RuntimeError("something else went wrong")

        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source.asyncio.sleep",
            new=AsyncMock(),
        ):
            with self.assertRaises(RuntimeError, msg="Should re-raise non-disconnect RuntimeError"):
                await self.data_source._ping_loop(self.ws_assistant)

    async def test_ping_loop_logs_warning_on_generic_exception(self):
        """Non-RuntimeError exception in ping loop logs warning (lines 216-218)."""
        logger = MagicMock()
        self.data_source.logger = MagicMock(return_value=logger)
        self.ws_assistant.send.side_effect = [ValueError("unexpected"), asyncio.CancelledError()]

        with patch(
            "hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source.asyncio.sleep",
            new=AsyncMock(),
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source._ping_loop(self.ws_assistant)

        logger.warning.assert_called()
