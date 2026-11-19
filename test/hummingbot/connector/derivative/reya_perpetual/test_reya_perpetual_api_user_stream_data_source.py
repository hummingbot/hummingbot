import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from hummingbot.connector.derivative.reya_perpetual.reya_perpetual_api_user_stream_data_source import (
    ReyaPerpetualAPIUserStreamDataSource,
)

WALLET = "0xF39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


class MockWSAssistant:
    def __init__(self, fail: bool = False):
        self.sent = []
        self.fail = fail
        self.disconnected = False

    async def send(self, request):
        if self.fail:
            raise ConnectionError("closed")
        self.sent.append(request.payload)

    async def disconnect(self):
        self.disconnected = True


class ReyaPerpetualAPIUserStreamDataSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.data_source = ReyaPerpetualAPIUserStreamDataSource(WALLET, SimpleNamespace())
        self.data_source._sleep = AsyncMock()

    def channel(self, resource: str) -> str:
        return f"/v2/wallet/{WALLET.lower()}/{resource}"

    async def drain_resubscriptions(self):
        await asyncio.gather(*self.data_source._resubscribe_tasks)

    async def test_subscribes_to_the_wallet_channels(self):
        ws = MockWSAssistant()
        await self.data_source._subscribe_channels(ws)
        self.assertEqual([f"/v2/wallet/{WALLET.lower()}/{resource}"
                          for resource in ("orderChanges", "perpExecutions", "positions", "accountSummaries",
                                           "positionRisk")],
                         [payload["channel"] for payload in ws.sent])

    async def test_queues_snapshots_updates_and_errors_only(self):
        queue = asyncio.Queue()
        for message in ({"type": "subscribed", "channel": "c", "contents": []},
                        {"type": "channel_data", "channel": "c", "data": []},
                        {"type": "error", "channel": "c", "message": "rejected"},
                        {"type": "pong"}):
            await self.data_source._process_event_message(message, queue)
        self.assertEqual(3, queue.qsize())

    async def test_a_refused_subscription_is_retried_on_the_same_connection(self):
        ws = MockWSAssistant()
        self.data_source._ws_assistant = ws
        queue = asyncio.Queue()
        for resource in ("accountSummaries", "orderChanges"):
            await self.data_source._process_event_message(
                {"type": "error", "channel": self.channel(resource), "message": "unavailable"}, queue)
        # An error about another channel, or without one, is queued but not retried.
        await self.data_source._process_event_message({"type": "error", "message": "rejected"}, queue)
        await self.drain_resubscriptions()

        self.assertEqual(3, queue.qsize())
        self.assertEqual([{"type": "subscribe", "channel": self.channel("accountSummaries")},
                          {"type": "subscribe", "channel": self.channel("orderChanges")}], ws.sent)

    async def test_retries_back_off_until_the_subscription_succeeds(self):
        self.data_source._ws_assistant = MockWSAssistant()
        error = {"type": "error", "channel": self.channel("positionRisk"), "message": "valuation unavailable"}
        for _ in range(7):
            await self.data_source._process_event_message(error, asyncio.Queue())
            await self.drain_resubscriptions()
        await self.data_source._process_event_message(
            {"type": "subscribed", "channel": self.channel("positionRisk"), "contents": {"data": []}}, asyncio.Queue())
        await self.data_source._process_event_message(error, asyncio.Queue())
        await self.drain_resubscriptions()

        delays = [call.args[0] for call in self.data_source._sleep.await_args_list]
        for delay, base in zip(delays, (2, 4, 8, 16, 32, 60, 60, 2)):
            self.assertTrue(base <= delay <= base * 1.25, (delay, base))

    async def test_a_retry_is_dropped_when_the_connection_was_replaced_or_fails(self):
        old, failing = MockWSAssistant(), MockWSAssistant(fail=True)
        self.data_source._ws_assistant = old
        error = {"type": "error", "channel": self.channel("positionRisk"), "message": "valuation unavailable"}
        await self.data_source._process_event_message(error, asyncio.Queue())
        self.data_source._ws_assistant = MockWSAssistant()
        await self.drain_resubscriptions()
        self.assertEqual([], old.sent)

        self.data_source._ws_assistant = failing
        await self.data_source._process_event_message(error, asyncio.Queue())
        await self.drain_resubscriptions()  # The failure is logged, not raised.
        self.assertEqual([], failing.sent)

    async def test_an_interruption_cancels_pending_retries(self):
        self.data_source._sleep = AsyncMock(side_effect=lambda delay: asyncio.sleep(3600))
        ws = MockWSAssistant()
        self.data_source._ws_assistant = ws
        await self.data_source._process_event_message(
            {"type": "error", "channel": self.channel("accountSummaries"), "message": "valuation unavailable"},
            asyncio.Queue())
        task = next(iter(self.data_source._resubscribe_tasks))

        await self.data_source._on_user_stream_interruption(ws)
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(ws.disconnected)
        self.assertEqual(set(), self.data_source._resubscribe_tasks)
