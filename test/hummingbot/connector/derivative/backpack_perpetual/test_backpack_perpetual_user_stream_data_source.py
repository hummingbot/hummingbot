import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.derivative.backpack_perpetual import backpack_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_user_stream_data_source import (
    BackpackPerpetualUserStreamDataSource,
)


class BackpackPerpetualUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.trading_pair = "BTC-USDC"
        self.auth = MagicMock()
        self.auth.generate_ws_auth_payload = MagicMock(
            return_value={
                "method": "SUBSCRIBE",
                "params": [
                    CONSTANTS.WS_ORDER_UPDATE_CHANNEL,
                    CONSTANTS.WS_POSITION_UPDATE_CHANNEL,
                ],
            }
        )
        self.connector = MagicMock()
        self.api_factory = MagicMock()
        self.data_source = BackpackPerpetualUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.api_factory,
            domain=CONSTANTS.DOMAIN,
        )

    async def test_subscribe_channels_sends_auth_payload(self):
        ws = AsyncMock()
        await self.data_source._subscribe_channels(ws)
        sent_request = ws.send.call_args[0][0]
        self.assertEqual(
            [CONSTANTS.WS_ORDER_UPDATE_CHANNEL, CONSTANTS.WS_POSITION_UPDATE_CHANNEL],
            sent_request.payload["params"],
        )
        self.assertTrue(sent_request.is_auth_required)

    def test_last_recv_time(self):
        ws = MagicMock()
        ws.last_recv_time = 456.0
        self.data_source._ws_assistant = ws
        self.assertEqual(456.0, self.data_source.last_recv_time)

    async def test_get_ws_assistant_uses_factory(self):
        ws = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=ws)
        result = await self.data_source._get_ws_assistant()
        self.assertEqual(ws, result)

    async def test_connected_websocket_assistant_connects(self):
        ws = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=ws)
        async def _noop_ping_thread(*args, **kwargs):
            return None
        with patch.object(self.data_source, "_ping_thread", side_effect=_noop_ping_thread):
            with patch(
                "hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_user_stream_data_source.safe_ensure_future",
                side_effect=lambda coro: asyncio.create_task(coro),
            ):
                result = await self.data_source._connected_websocket_assistant()
        self.assertEqual(ws, result)
        ws.connect.assert_awaited_once()

    async def test_process_event_message_raises_on_error(self):
        queue = asyncio.Queue()
        event_message = {"error": {"message": "boom"}}
        with self.assertRaises(IOError):
            await self.data_source._process_event_message(event_message, queue)

    async def test_process_event_message_raises_on_error_string(self):
        queue = asyncio.Queue()
        event_message = {"error": "boom"}
        with self.assertRaises(IOError):
            await self.data_source._process_event_message(event_message, queue)

    async def test_process_event_message_ignores_subscription_confirmation(self):
        queue = asyncio.Queue()
        event_message = {"result": "success"}
        await self.data_source._process_event_message(event_message, queue)
        self.assertTrue(queue.empty())

    async def test_process_event_message_enqueues_stream_messages(self):
        queue = asyncio.Queue()
        event_message = {"stream": "account.positionUpdate", "data": {"e": "positionUpdate"}}
        await self.data_source._process_event_message(event_message, queue)
        self.assertFalse(queue.empty())

    async def test_process_event_message_enqueues_event_type_messages(self):
        queue = asyncio.Queue()
        event_message = {"data": {"e": "positionUpdate"}}
        await self.data_source._process_event_message(event_message, queue)
        self.assertFalse(queue.empty())

    async def test_process_websocket_messages_sends_ping_on_timeout(self):
        ws = AsyncMock()
        queue = asyncio.Queue()
        with patch(
            "hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._process_websocket_messages",
            new_callable=AsyncMock,
            side_effect=[asyncio.TimeoutError(), asyncio.CancelledError()],
        ):
            with self.assertRaises(asyncio.CancelledError):
                await self.data_source._process_websocket_messages(ws, queue)
        ws.ping.assert_awaited()

    async def test_ping_thread_sends_ping(self):
        ws = AsyncMock()
        with patch(
            "hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_user_stream_data_source.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=[None, asyncio.CancelledError()],
        ):
            await self.data_source._ping_thread(ws)
        ws.ping.assert_awaited_once()

    async def test_ping_thread_logs_exception(self):
        ws = AsyncMock()
        ws.ping = AsyncMock(side_effect=Exception("boom"))
        with patch(
            "hummingbot.connector.derivative.backpack_perpetual.backpack_perpetual_user_stream_data_source.asyncio.sleep",
            new_callable=AsyncMock,
            return_value=None,
        ):
            await self.data_source._ping_thread(ws)
