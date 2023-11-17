import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.errors import (
    PipeFullError,
    PipeSentinelError,
    PipeStoppedError,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.sentinel import SENTINEL, sentinel_ize
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.utilities import pipe_snapshot


class TestPipe(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    async def asyncSetUp(self):
        self.pipe = Pipe[int](maxsize=2)
        self.set_loggers([self.pipe.logger()])

    async def put_values_in_queue(self, values):
        # Wait a bit before starting to put values in the queue, to ensure that iteration has already started
        await asyncio.sleep(0.1)
        for value in values:
            await self.pipe.put(value)
        await self.pipe.stop()

    async def continual_put_in_queue(self):
        i = 0
        while True:
            try:
                with patch.object(Pipe, "logger"):
                    await self.pipe.put(i)
            except Exception:
                break
            i += 1
            await asyncio.sleep(0.05)  # simulate delay

    async def test_put_on_condition_space_available(self):
        self.pipe._pipe = MagicMock()
        self.pipe._pipe.full.return_value = False
        self.pipe._space_available = asyncio.Condition()

        await self.pipe._put_on_condition('some_item')

        self.pipe._pipe.put_nowait.assert_called_once_with('some_item')

    async def test_put_on_condition_space_not_available(self):
        async def release_condition(condition):
            async with condition:
                condition.notify_all()

        self.pipe._pipe = MagicMock()
        self.pipe._pipe.full.side_effect = [True, False]  # Simulate that the queue is initially full
        self.pipe._space_available = asyncio.Condition()

        asyncio.create_task(release_condition(self.pipe._space_available))  # Simulate external event
        await self.pipe._put_on_condition('some_item')

        self.assertEqual(self.pipe._pipe.full.call_count, 2)
        self.pipe._pipe.put_nowait.assert_called_once_with('some_item')

    async def test_put_on_condition_timeout(self):
        self.pipe._pipe = MagicMock()
        self.pipe._pipe.full.return_value = True

        with self.assertRaises(PipeFullError):
            await self.pipe._put_on_condition('some_item', timeout=0.1)

    async def test_put(self):
        await self.pipe.put(1)
        self.assertEqual(await self.pipe._pipe.get(), 1)

    async def test_put_when_stopped(self):
        await self.pipe.stop()
        with self.assertRaises(PipeStoppedError):
            await self.pipe.put(1)

    async def test_put_sentinel_when_stopped(self):
        with self.assertRaises(PipeSentinelError):
            await self.pipe.put(SENTINEL)  # This should not raise an error

    async def test_put_sentinel(self):
        await self.pipe._put_sentinel()
        item = await self.pipe.get()
        self.assertIs(SENTINEL, item)

    async def test_get(self):
        await self.pipe.put(1)
        self.assertEqual(await self.pipe.get(), 1)

    async def test_stop(self):
        await self.pipe.stop()
        self.assertTrue(self.pipe.is_stopped)
        self.assertEqual((SENTINEL,), await pipe_snapshot(self.pipe))

    async def test_snapshot(self):
        items = (1, 2)
        for item in items:
            await self.pipe.put(item)
        snapshot = await pipe_snapshot(self.pipe)
        self.assertTupleEqual(items, snapshot)
        self.assertTrue(self.pipe._pipe.empty)

    async def test_continual_put_in_queue_gets_full_and_stopped(self):
        asyncio.create_task(self.continual_put_in_queue())
        await asyncio.sleep(0.5)  # allow queue to get full
        await self.pipe.stop()
        self.assertTrue(self.pipe.is_stopped)
        self.assertEqual(2, self.pipe.size)
        self.assertEqual((0, 1), await pipe_snapshot(self.pipe))

    async def test_put_into_stopped_pipe_raises_error(self):
        await self.pipe.stop()
        with self.assertRaises(PipeStoppedError):
            await self.pipe.put(1)

    async def test_put_handles_queue_full(self):
        await self.pipe.put(1)
        await self.pipe.put(2)

        with patch.object(Pipe, "logger") as mock_logger:
            with self.assertRaises(PipeFullError):
                await self.pipe.put(3, timeout=0.5)
        mock_logger.assert_called()

    async def test_task_done_and_join(self):
        await self.pipe.put(1)
        # get() calls task_done() internally, by default
        data = await self.pipe.get()
        self.assertEqual(1, data)

        # get() calls task_done() internally
        with self.assertRaises(ValueError):
            self.pipe._pipe.task_done()

        # Pipe itself silently ignores task_done() calls by default
        self.pipe.task_done()

        join_task = asyncio.create_task(self.pipe.join())
        await asyncio.sleep(0.1)  # Give the join task some time to run
        self.assertTrue(join_task.done())

    async def test_task_done_and_join_when_get_not_performing_task_done(self):
        self.pipe._perform_task_done = False

        await self.pipe.put(1)
        # get() calls task_done() internally, by default
        data = await self.pipe.get()
        self.assertEqual(1, data)

        # get() does not call task_done()
        self.pipe._pipe.task_done()

        # task_done() calls _pipe.task_done() and thus raises an error if called too many times
        with self.assertRaises(ValueError):
            self.pipe.task_done()

        join_task = asyncio.create_task(self.pipe.join())
        await asyncio.sleep(0.1)  # Give the join task some time to run
        self.assertTrue(join_task.done())

    async def test_sentinel_ize(self):
        items = (1, 2, 3)
        sentinelized_items = sentinel_ize(items)
        self.assertEqual(sentinelized_items, (1, 2, 3, SENTINEL))

    async def test_sentinel_ize_with_existing_sentinel(self):
        items = (1, 2, SENTINEL, 3)
        sentinelized_items = sentinel_ize(items)
        self.assertEqual((1, 2, SENTINEL), sentinelized_items, )

    async def test_stop_when_full(self):
        await self.pipe.put(1)
        await self.pipe.put(2)
        await self.pipe.stop()
        self.assertEqual(self.pipe._sentinel_position, 2)
        self.assertEqual(await self.pipe.get(), 1)
        self.assertEqual(await self.pipe.get(), 2)
        self.assertEqual(await self.pipe.get(), SENTINEL)

    async def test_stop_when_not_full(self):
        await self.pipe.put(1)
        await self.pipe.stop()
        self.assertEqual(self.pipe._sentinel_position, -1)
        self.assertEqual(await self.pipe.get(), 1)
        self.assertEqual(await self.pipe.get(), SENTINEL)
