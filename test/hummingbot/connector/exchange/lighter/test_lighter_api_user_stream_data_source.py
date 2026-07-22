import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.exchange.lighter import lighter_constants as CONSTANTS
from hummingbot.connector.exchange.lighter.lighter_api_user_stream_data_source import LighterAPIUserStreamDataSource


class MockWSAssistant:
    def __init__(self):
        self.sent = []
        self.connect_calls = []
        self.last_recv_time = 123

    async def connect(self, **kwargs):
        self.connect_calls.append(kwargs)

    async def send(self, request):
        self.sent.append(request)


class LighterAPIUserStreamDataSourceTests(TestCase):
    def test_last_recv_time_returns_zero_without_ws(self):
        data_source = LighterAPIUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )

        self.assertEqual(0, data_source.last_recv_time)

    def test_last_recv_time_returns_ws_time(self):
        data_source = LighterAPIUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )
        data_source._ws_assistant = SimpleNamespace(last_recv_time=456)

        self.assertEqual(456, data_source.last_recv_time)

    def test_connected_websocket_assistant_ensures_account_and_uses_connector_factory(self):
        # Regression for the "auth field is required" private-websocket failure: the assistant
        # must be built from the connector's *current* (authenticated) factory, not the possibly
        # auth-less one captured at construction, and only after the account bootstrap completes.
        ws = MockWSAssistant()
        connector_factory = SimpleNamespace(get_ws_assistant=AsyncMock(return_value=ws))
        connector = SimpleNamespace(
            _ensure_account_ready=AsyncMock(),
            _web_assistants_factory=connector_factory,
        )
        stale_factory = SimpleNamespace(get_ws_assistant=AsyncMock())
        data_source = LighterAPIUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=connector,
            api_factory=stale_factory,
        )

        connected_ws = asyncio.run(data_source._connected_websocket_assistant())

        self.assertEqual(ws, connected_ws)
        connector._ensure_account_ready.assert_awaited_once()
        connector_factory.get_ws_assistant.assert_awaited_once()
        stale_factory.get_ws_assistant.assert_not_called()
        self.assertEqual(CONSTANTS.PRIVATE_WS_PING_INTERVAL, ws.connect_calls[0]["ping_timeout"])

    def test_subscribe_channels_inject_auth_token(self):
        # End-to-end: a real WSAssistant carrying a real LighterAuth must stamp the `auth` token
        # onto every private subscribe message (guards against the missing-auth regression).
        from hummingbot.connector.exchange.lighter.lighter_auth import LighterAuth
        from hummingbot.core.web_assistant.ws_assistant import WSAssistant

        signer = SimpleNamespace(
            create_auth_token_with_expiry=lambda deadline, api_key_index: ("tok-123", None)
        )
        auth = LighterAuth(signer_client=signer, api_key_index=2)
        sent = []
        connection = SimpleNamespace(send=AsyncMock(side_effect=lambda request: sent.append(request)))
        ws_assistant = WSAssistant(connection=connection, auth=auth)

        data_source = LighterAPIUserStreamDataSource(
            auth=auth,
            connector=SimpleNamespace(account_index=724450),
            api_factory=SimpleNamespace(),
        )

        asyncio.run(data_source._subscribe_channels(ws_assistant))

        self.assertEqual(3, len(sent))
        for request in sent:
            self.assertEqual("tok-123", request.payload["auth"])
            self.assertTrue(str(request.payload["channel"]).endswith("/724450"))

    def test_subscribe_channels_sends_private_channel_requests(self):
        data_source = LighterAPIUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(account_index=724450),
            api_factory=SimpleNamespace(),
        )
        ws = MockWSAssistant()

        asyncio.run(data_source._subscribe_channels(ws))

        self.assertEqual(3, len(ws.sent))
        self.assertEqual({"type": "subscribe", "channel": "account_all_orders/724450"}, ws.sent[0].payload)
        self.assertEqual({"type": "subscribe", "channel": "account_all_trades/724450"}, ws.sent[1].payload)
        self.assertEqual({"type": "subscribe", "channel": "account_all_assets/724450"}, ws.sent[2].payload)
        self.assertTrue(all(request.is_auth_required for request in ws.sent))

    def test_process_event_message_routes_private_channels(self):
        data_source = LighterAPIUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )
        queue = asyncio.Queue()
        message = {"channel": "account_all_assets:724450", "assets": {}}

        asyncio.run(data_source._process_event_message(message, queue))

        self.assertEqual(message, queue.get_nowait())

    def test_process_event_message_ignores_unknown_channel_and_raises_error(self):
        data_source = LighterAPIUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )
        queue = asyncio.Queue()

        asyncio.run(data_source._process_event_message({"channel": "trade:1"}, queue))
        self.assertTrue(queue.empty())

        with self.assertRaises(IOError):
            asyncio.run(data_source._process_event_message({"error": "boom"}, queue))
