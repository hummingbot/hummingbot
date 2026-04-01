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

    async def test_process_event_message_enqueues_account_messages(self):
        queue = asyncio.Queue()
        message = {"type": "update/account_all", "channel": "account_all:123", "account": {"assets": []}}

        await self.data_source._process_event_message(message, queue)

        queued = queue.get_nowait()
        self.assertEqual(message, queued)
