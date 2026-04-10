import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import LighterAPIUserStreamDataSource
from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth


class LighterAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.connector = MagicMock()
        self.connector.rest_api_key = "api-key"
        self.auth = LighterAuth(api_key="api-key", account_identifier="123")
        self.data_source = LighterAPIUserStreamDataSource(
            connector=self.connector,
            api_factory=MagicMock(),
            auth=self.auth,
        )

    async def test_connected_websocket_assistant_connects_with_api_key_header(self):
        ws = MagicMock()
        ws.connect = AsyncMock()
        self.data_source._api_factory.get_ws_assistant = AsyncMock(return_value=ws)

        connected_ws = await self.data_source._connected_websocket_assistant()

        self.assertIs(ws, connected_ws)
        ws.connect.assert_awaited_once_with(
            ws_url="wss://mainnet.zklighter.elliot.ai/stream",
            ws_headers={"X-Api-Key": "api-key"},
        )

    async def test_subscribe_channels_sends_account_subscription(self):
        ws = MagicMock()
        ws.receive = AsyncMock(return_value=MagicMock(data={"type": "connected"}))
        ws.send = AsyncMock()

        await self.data_source._subscribe_channels(ws)

        sent_payload = ws.send.await_args.args[0].payload
        self.assertEqual({"type": "subscribe", "channel": "account_all/123"}, sent_payload)

    async def test_subscribe_channels_raises_when_not_connected(self):
        ws = MagicMock()
        ws.receive = AsyncMock(return_value=MagicMock(data={"type": "error"}))

        with self.assertRaises(IOError):
            await self.data_source._subscribe_channels(ws)

    async def test_process_websocket_messages_replies_to_ping_and_processes_events(self):
        websocket_assistant = MagicMock()
        websocket_assistant.send = AsyncMock()
        queue = asyncio.Queue()

        async def iter_messages():
            yield MagicMock(data={"type": "ping"})
            yield MagicMock(data={"type": "update/account_all", "channel": "account_all:123", "data": {}})

        websocket_assistant.iter_messages = iter_messages
        self.data_source._process_event_message = AsyncMock()

        await self.data_source._process_websocket_messages(websocket_assistant, queue)

        websocket_assistant.send.assert_awaited_once()
        self.data_source._process_event_message.assert_awaited_once_with(
            event_message={"type": "update/account_all", "channel": "account_all:123", "data": {}},
            queue=queue,
        )

    async def test_process_event_message_enqueues_account_messages(self):
        queue = asyncio.Queue()
        message = {"type": "update/account_all", "channel": "account_all:123", "account": {"assets": []}}

        await self.data_source._process_event_message(message, queue)

        queued = queue.get_nowait()
        self.assertEqual(message, queued)

    async def test_process_event_message_ignores_unknown_messages(self):
        queue = asyncio.Queue()

        await self.data_source._process_event_message({"type": "other", "channel": "other:123"}, queue)

        self.assertTrue(queue.empty())
