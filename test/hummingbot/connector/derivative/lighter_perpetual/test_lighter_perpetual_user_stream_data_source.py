import asyncio
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock

from hummingbot.connector.derivative.lighter_perpetual import lighter_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.lighter_perpetual.lighter_perpetual_user_stream_data_source import (
    LighterPerpetualUserStreamDataSource,
)


class MockWSAssistant:
    def __init__(self):
        self.sent = []
        self.connect_calls = []
        self.last_recv_time = 123

    async def connect(self, **kwargs):
        self.connect_calls.append(kwargs)

    async def send(self, request):
        self.sent.append(request)


class LighterPerpetualUserStreamDataSourceTests(TestCase):
    def test_last_recv_time_returns_zero_without_ws(self):
        data_source = LighterPerpetualUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )

        self.assertEqual(0, data_source.last_recv_time)

    def test_last_recv_time_returns_ws_time(self):
        data_source = LighterPerpetualUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )
        data_source._ws_assistant = SimpleNamespace(last_recv_time=456)

        self.assertEqual(456, data_source.last_recv_time)

    def test_connected_websocket_assistant_reuses_ws(self):
        ws = MockWSAssistant()
        api_factory = SimpleNamespace(get_ws_assistant=AsyncMock(return_value=ws))
        data_source = LighterPerpetualUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=api_factory,
        )

        connected_ws = asyncio.run(data_source._connected_websocket_assistant())
        connected_ws_again = asyncio.run(data_source._connected_websocket_assistant())

        self.assertEqual(ws, connected_ws)
        self.assertEqual(ws, connected_ws_again)
        self.assertEqual(1, api_factory.get_ws_assistant.await_count)
        self.assertEqual(CONSTANTS.PRIVATE_WS_PING_INTERVAL, ws.connect_calls[0]["ping_timeout"])

    def test_subscribe_channels_sends_private_channel_requests(self):
        data_source = LighterPerpetualUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(account_index=724450),
            api_factory=SimpleNamespace(),
        )
        ws = MockWSAssistant()

        asyncio.run(data_source._subscribe_channels(ws))

        self.assertEqual(4, len(ws.sent))
        self.assertEqual({"type": "subscribe", "channel": "account_all_orders/724450"}, ws.sent[0].payload)
        self.assertEqual({"type": "subscribe", "channel": "account_all_trades/724450"}, ws.sent[1].payload)
        self.assertEqual({"type": "subscribe", "channel": "account_all_assets/724450"}, ws.sent[2].payload)
        self.assertEqual({"type": "subscribe", "channel": "account_all_positions/724450"}, ws.sent[3].payload)
        self.assertTrue(all(request.is_auth_required for request in ws.sent))

    def test_process_event_message_routes_private_channels(self):
        data_source = LighterPerpetualUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )
        queue = asyncio.Queue()
        message = {"channel": "account_all_positions:724450", "positions": {}}

        asyncio.run(data_source._process_event_message(message, queue))

        self.assertEqual(message, queue.get_nowait())

    def test_process_event_message_ignores_unknown_channel_and_raises_error(self):
        data_source = LighterPerpetualUserStreamDataSource(
            auth=SimpleNamespace(),
            connector=SimpleNamespace(),
            api_factory=SimpleNamespace(),
        )
        queue = asyncio.Queue()

        asyncio.run(data_source._process_event_message({"channel": "trade:1"}, queue))
        self.assertTrue(queue.empty())

        with self.assertRaises(IOError):
            asyncio.run(data_source._process_event_message({"error": "boom"}, queue))
