import asyncio
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.kuru.kuru_api_user_stream_data_source import KuruAPIUserStreamDataSource


class TestKuruAPIUserStreamDataSource(TestCase):

    def setUp(self):
        self.connector = MagicMock()
        self.data_source = KuruAPIUserStreamDataSource(connector=self.connector)

    def test_last_recv_time_returns_float(self):
        result = self.data_source.last_recv_time
        self.assertIsInstance(result, float)

    def test_last_recv_time_is_recent(self):
        import time
        before = time.time()
        result = self.data_source.last_recv_time
        after = time.time()
        self.assertGreaterEqual(result, before)
        self.assertLessEqual(result, after)

    def test_connected_websocket_assistant_raises_not_implemented(self):
        coro = self.data_source._connected_websocket_assistant()
        with self.assertRaises(NotImplementedError) as ctx:
            asyncio.run(coro)
        self.assertIn("SDK callbacks", str(ctx.exception))

    def test_subscribe_channels_raises_not_implemented(self):
        coro = self.data_source._subscribe_channels(websocket_assistant=MagicMock())
        with self.assertRaises(NotImplementedError) as ctx:
            asyncio.run(coro)
        self.assertIn("SDK callbacks", str(ctx.exception))


class TestKuruAPIUserStreamDataSourceAsync(IsolatedAsyncioTestCase):

    def setUp(self):
        self.connector = MagicMock()
        self.data_source = KuruAPIUserStreamDataSource(connector=self.connector)

    async def test_listen_for_user_stream_runs_indefinitely(self):
        """listen_for_user_stream should block (sleep forever); cancel it after a short wait."""
        output_queue = asyncio.Queue()
        task = asyncio.ensure_future(self.data_source.listen_for_user_stream(output_queue))

        # Give the coroutine a moment to reach the sleep
        await asyncio.sleep(0.05)

        # The task should still be running (not done)
        self.assertFalse(task.done())

        # Clean up: cancel the task
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass

        # Output queue should be empty — no events were emitted
        self.assertTrue(output_queue.empty())
