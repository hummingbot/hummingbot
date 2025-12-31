import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.backpack import backpack_constants as CONSTANTS
from hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source import (
    BackpackAPIUserStreamDataSource,
)


class BackpackAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.trading_pair = "BTC-USDC"
        self.auth = MagicMock()
        self.auth.generate_ws_auth_payload = MagicMock(
            return_value={"method": "SUBSCRIBE", "params": [CONSTANTS.WS_ORDER_UPDATE_CHANNEL]}
        )
        self.connector = MagicMock()
        self.api_factory = MagicMock()
        self.data_source = BackpackAPIUserStreamDataSource(
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
        self.assertEqual(["account.orderUpdate"], sent_request.payload["params"])
        self.assertTrue(sent_request.is_auth_required)

    async def test_process_event_message_raises_on_error(self):
        queue = asyncio.Queue()
        event_message = {"error": {"message": "boom"}}
        with self.assertRaises(IOError):
            await self.data_source._process_event_message(event_message, queue)

    async def test_process_event_message_ignores_subscription_confirmation(self):
        queue = asyncio.Queue()
        event_message = {"result": "success"}
        await self.data_source._process_event_message(event_message, queue)
        self.assertTrue(queue.empty())

    async def test_process_event_message_enqueues_stream_messages(self):
        queue = asyncio.Queue()
        event_message = {"stream": "account.orderUpdate", "data": {"e": "orderUpdate"}}
        await self.data_source._process_event_message(event_message, queue)
        self.assertFalse(queue.empty())

    async def test_process_event_message_enqueues_event_type_messages(self):
        queue = asyncio.Queue()
        event_message = {"data": {"e": "orderUpdate"}}
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
            "hummingbot.connector.exchange.backpack.backpack_api_user_stream_data_source.asyncio.sleep",
            new_callable=AsyncMock,
            side_effect=[None, asyncio.CancelledError()],
        ):
            await self.data_source._ping_thread(ws)
        ws.ping.assert_awaited_once()
