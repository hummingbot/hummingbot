import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.derivative.drift_perpetual import drift_perpetual_constants as CONSTANTS
from hummingbot.connector.derivative.drift_perpetual.drift_perpetual_api_user_stream_data_source import (
    DriftPerpetualAPIUserStreamDataSource,
)


class DriftPerpetualAPIUserStreamDataSourceTests(IsolatedAsyncioWrapperTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.connector = MagicMock()
        self.connector.sub_account_id = 0
        self.connector.drift_gateway_ws_url = "ws://127.0.0.1:1337"
        self.data_source = DriftPerpetualAPIUserStreamDataSource(
            api_factory=MagicMock(), connector=self.connector
        )

    def test_last_recv_time_defaults_to_minus_one(self):
        # No websocket connected yet.
        self.assertEqual(-1, self.data_source.last_recv_time)

    def test_last_recv_time_proxies_ws_assistant(self):
        ws = MagicMock()
        ws.last_recv_time = 1_715_770_500.0
        self.data_source._ws_assistant = ws
        self.assertEqual(1_715_770_500.0, self.data_source.last_recv_time)

    async def test_subscribe_channels_sends_single_subaccount_subscribe(self):
        self.connector.sub_account_id = 3
        ws = AsyncMock()
        await self.data_source._subscribe_channels(ws)
        ws.send.assert_called_once()
        sent = ws.send.call_args.args[0]
        # One subscribe delivers orders+fills+funding for the sub-account.
        self.assertEqual(CONSTANTS.WS_METHOD_SUBSCRIBE, sent.payload["method"])
        self.assertEqual(3, sent.payload["subAccountId"])

    async def test_process_event_message_forwards_known_channels(self):
        queue: asyncio.Queue = asyncio.Queue()
        for channel in (CONSTANTS.WS_CHANNEL_ORDERS, CONSTANTS.WS_CHANNEL_FILLS, CONSTANTS.WS_CHANNEL_FUNDING):
            msg = {"channel": channel, "data": {"x": 1}, "subAccountId": 0}
            await self.data_source._process_event_message(msg, queue)
        self.assertEqual(3, queue.qsize())
        self.assertEqual(CONSTANTS.WS_CHANNEL_ORDERS, queue.get_nowait()["channel"])

    async def test_process_event_message_ignores_acks_and_heartbeats(self):
        queue: asyncio.Queue = asyncio.Queue()
        # subscribe ack / heartbeat: no data, or unknown channel, or no channel
        await self.data_source._process_event_message({"channel": "orders"}, queue)            # data None
        await self.data_source._process_event_message({"channel": "heartbeat", "data": {}}, queue)
        await self.data_source._process_event_message({"data": {"x": 1}}, queue)               # no channel
        await self.data_source._process_event_message({"channel": "orders", "data": None}, queue)
        self.assertTrue(queue.empty())

    async def test_process_event_message_ignores_non_dict(self):
        queue: asyncio.Queue = asyncio.Queue()
        for bad in ("not-a-dict", None, 42, ["orders"]):
            await self.data_source._process_event_message(bad, queue)
        self.assertTrue(queue.empty())
