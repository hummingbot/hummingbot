import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.vest_perpetual import vest_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.vest_perpetual.vest_perpetual_user_stream_data_source import (
    VestPerpetualUserStreamDataSource,
)
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


class _DummyConnector:
    def __init__(self):
        self._account_group = 5
        self.domain = CONSTANTS.DEFAULT_DOMAIN


class VestPerpetualUserStreamDataSourceTests(IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        self.connector = _DummyConnector()
        self.auth = MagicMock()
        self.api_factory = MagicMock()
        self.rest_assistant = AsyncMock()
        self.api_factory.get_rest_assistant = AsyncMock(return_value=self.rest_assistant)
        self.ws_assistant = AsyncMock()
        self.ws_assistant.connect = AsyncMock()
        self.ws_assistant.send = AsyncMock()
        self.api_factory.get_ws_assistant = AsyncMock(return_value=self.ws_assistant)
        self.data_source = VestPerpetualUserStreamDataSource(
            auth=self.auth,
            connector=self.connector,
            api_factory=self.api_factory,
        )

    async def test_get_listen_key_requests_authenticated_endpoint(self):
        self.rest_assistant.execute_request = AsyncMock(return_value={"listenKey": "abc"})

        await self.data_source._get_listen_key()

        self.rest_assistant.execute_request.assert_awaited_with(
            url=f"{CONSTANTS.REST_URL_PROD}{CONSTANTS.LISTEN_KEY_PATH_URL}",
            throttler_limit_id=CONSTANTS.LISTEN_KEY_PATH_URL,
            method=RESTMethod.POST,
            is_auth_required=True,
        )
        self.assertEqual("abc", self.data_source._listen_key)

    async def test_connected_websocket_assistant_uses_private_ws_url(self):
        self.rest_assistant.execute_request = AsyncMock(return_value={"listenKey": "listen"})

        ws = await self.data_source._connected_websocket_assistant()

        self.ws_assistant.connect.assert_awaited()
        args, kwargs = self.ws_assistant.connect.await_args
        self.assertIn("listenKey=listen", kwargs["ws_url"])
        self.assertIs(ws, self.ws_assistant)

    async def test_subscribe_channels_sends_single_request(self):
        self.rest_assistant.execute_request = AsyncMock(return_value={"listenKey": "listen"})
        await self.data_source._connected_websocket_assistant()

        await self.data_source._subscribe_channels(self.ws_assistant)

        self.ws_assistant.send.assert_awaited_once()
        request = self.ws_assistant.send.await_args.args[0]
        self.assertIn(CONSTANTS.WS_ACCOUNT_PRIVATE_CHANNEL, request.payload["params"])

    async def test_process_websocket_messages_filters_by_channel(self):
        queue: asyncio.Queue = asyncio.Queue()

        class _Message:
            def __init__(self, data):
                self.data = data

        class _WS:
            async def iter_messages(self_inner):
                for payload in [
                    _Message({"channel": "other", "data": {"id": 0}}),
                    _Message({"channel": CONSTANTS.WS_ACCOUNT_PRIVATE_CHANNEL, "data": {"id": 1}}),
                ]:
                    yield payload

        await self.data_source._process_websocket_messages(_WS(), queue)

        event = await queue.get()
        self.assertEqual(1, event["data"]["id"])
        self.assertTrue(queue.empty())
