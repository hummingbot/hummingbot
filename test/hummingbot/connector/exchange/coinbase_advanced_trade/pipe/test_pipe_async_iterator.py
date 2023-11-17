import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase

from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import Pipe, PipeAsyncIterator


class TestPipeAsyncIterator(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        self.pipe = Pipe[int](maxsize=5)
        self.iterator = PipeAsyncIterator(self.pipe)

    async def test_iteration(self):
        items = [1, 2, 3]
        for item in items:
            await self.pipe.put(item)
        await self.pipe._put_sentinel()
        async for item in self.iterator:
            self.assertEqual(item, items.pop(0))
        self.assertEqual(0, len(items))

    async def test_stop_iteration(self):
        items = [1, 2, 3]
        for item in items:
            await self.pipe.put(item)
        await self.pipe.stop()
        async for item in self.iterator:
            self.assertEqual(item, items.pop(0))
        self.assertEqual(0, len(items))

    async def test_cancelled_error(self):
        items = [1, 2, 3]
        for item in items:
            await self.pipe.put(item)

        async def iterate():
            async for item in self.iterator:
                pass

        task = asyncio.create_task(iterate())
        task.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await task
