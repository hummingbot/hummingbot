import asyncio
import unittest
from types import SimpleNamespace

from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_api_user_stream_data_source import (
    ReyaPerpetualAPIUserStreamDataSource,
)

WALLET = "0xF39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


class MockWSAssistant:
    def __init__(self):
        self.sent = []

    async def send(self, request):
        self.sent.append(request.payload)


class ReyaPerpetualAPIUserStreamDataSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.data_source = ReyaPerpetualAPIUserStreamDataSource(WALLET, SimpleNamespace())

    async def test_subscribes_to_the_wallet_channels(self):
        ws = MockWSAssistant()
        await self.data_source._subscribe_channels(ws)
        self.assertEqual([f"/v2/wallet/{WALLET.lower()}/{resource}"
                          for resource in ("orderChanges", "perpExecutions", "positions", "accountSummaries")],
                         [payload["channel"] for payload in ws.sent])

    async def test_queues_snapshots_updates_and_errors_only(self):
        queue = asyncio.Queue()
        for message in ({"type": "subscribed", "channel": "c", "contents": []},
                        {"type": "channel_data", "channel": "c", "data": []},
                        {"type": "error", "channel": "c", "message": "rejected"},
                        {"type": "pong"}):
            await self.data_source._process_event_message(message, queue)
        self.assertEqual(3, queue.qsize())
