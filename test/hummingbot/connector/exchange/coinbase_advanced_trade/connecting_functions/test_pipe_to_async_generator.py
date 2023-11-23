import asyncio
import gc
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

import objgraph

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import pipe_to_async_generator
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import SENTINEL


class CustomException(Exception):
    pass


class TestPipeToAsyncGenerator(IsolatedAsyncioWrapperTestCase):

    async def test_normal_operation(self):
        pipe = AsyncMock()
        pipe.task_done = MagicMock()
        pipe.get.side_effect = [1, 2, 3, SENTINEL]
        async_gen = pipe_to_async_generator(pipe)

        result = [i async for i in async_gen]
        self.assertEqual(result, [1, 2, 3])
        self.assertEqual(1, pipe.task_done.call_count)

    async def test_normal_operation_memory(self):
        pipe = AsyncMock()
        pipe.task_done = MagicMock()
        pipe.get.side_effect = [1, 2, 3, SENTINEL]
        objgraph.show_growth(limit=1)
        async_gen = pipe_to_async_generator(pipe)
        _ = [i async for i in async_gen]
        del async_gen
        del pipe
        gc.collect()
        print("- Diff -")
        objgraph.show_growth()

    async def test_sentinel_handling(self):
        pipe = MagicMock()
        pipe.get = AsyncMock(side_effect=[SENTINEL])
        on_sentinel_stop = AsyncMock()
        async_gen = pipe_to_async_generator(pipe, on_sentinel_stop=on_sentinel_stop)

        result = [i async for i in async_gen]
        self.assertEqual(result, [])
        self.assertEqual(1, pipe.task_done.call_count)
        on_sentinel_stop.assert_awaited_once()

    async def test_on_condition(self):
        pipe = MagicMock()
        pipe.get = AsyncMock(side_effect=[1, 2, 3, SENTINEL])

        def on_condition(x):
            return x % 2 == 0

        async_gen = pipe_to_async_generator(pipe, on_condition=on_condition)

        result = [i async for i in async_gen]
        self.assertEqual(result, [2])
        self.assertEqual(1, pipe.task_done.call_count)

    async def test_exception_in_pipe_get(self):
        pipe = MagicMock()
        pipe.get = AsyncMock(side_effect=[Exception("Error in get"), SENTINEL])
        async_gen = pipe_to_async_generator(pipe)

        with self.assertRaises(Exception):
            _ = [i async for i in async_gen]

    async def test_on_condition_raises_exception(self):
        pipe = MagicMock()
        pipe.get = AsyncMock(side_effect=[1, SENTINEL])

        def on_condition(x):
            if x == 1:
                raise Exception("Condition failed")
            return True

        async_gen = pipe_to_async_generator(pipe, on_condition=on_condition)

        with self.assertRaises(Exception):
            _ = [i async for i in async_gen]

    async def test_exception(self):
        pipe = AsyncMock()
        pipe.get.side_effect = [1, Exception("Error in get"), 2]
        custom_exception = CustomException
        async_gen = pipe_to_async_generator(pipe, exception=custom_exception)

        with self.assertRaises(CustomException):
            _ = [i async for i in async_gen]

    async def test_cancelled_parameter(self):
        pipe = AsyncMock()
        pipe.get.side_effect = [1, asyncio.CancelledError, 2]
        custom_exception = CustomException
        async_gen = pipe_to_async_generator(pipe, exception=custom_exception)

        result = [i async for i in async_gen]
        self.assertEqual([1], result)

    async def test_timeout_parameter(self):
        pipe = AsyncMock()
        pipe.get.side_effect = [1, asyncio.TimeoutError, 2]
        custom_exception = CustomException
        async_gen = pipe_to_async_generator(pipe, exception=custom_exception)

        result = [i async for i in async_gen]
        self.assertEqual([1], result)

    async def test_call_task_done_flag_false(self):
        pipe = AsyncMock()
        pipe.get.side_effect = [1, 2, 3, SENTINEL]
        async_gen = pipe_to_async_generator(pipe, call_task_done=False)

        result = [i async for i in async_gen]
        self.assertEqual(result, [1, 2, 3])
        pipe.task_done.assert_not_called()
