import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, call, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import pipe_to_async_generator
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.call_or_await import CallOrAwait
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.errors import (
    ConditionalPutError,
    DataGeneratorError,
    DestinationPutError,
    ExceptionWithItem,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.exception_log_manager import (
    raise_with_item,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.utilities import (
    data_to_async_generator,
    put_on_condition,
    transform_async_generator,
)


class _ExceptionWithItem(ExceptionWithItem):
    def __init__(self, item):
        super().__init__(msg=f"An error occurred with item: {item}", item=item)
        self.item = item


class TestCallOrAwait(IsolatedAsyncioWrapperTestCase):

    async def async_func(self, a, b):
        await asyncio.sleep(0.1)
        return a + b

    def sync_func(self, a, b):
        return a + b

    async def failing_func(self):
        raise ValueError("Test Error")

    async def test_async_function_call(self):
        wrapper = CallOrAwait(func=self.async_func, args=(10, 20))
        result = await wrapper.call()
        self.assertEqual(result, 30)

    async def test_sync_function_call(self):
        wrapper = CallOrAwait(func=self.sync_func, args=(10, 20))
        result = await wrapper.call()
        self.assertEqual(result, 30)

    async def test_exception_handling(self):
        async def failing_func():
            raise ValueError("Test Error")

        wrapper = CallOrAwait(func=failing_func)
        with self.assertRaises(ExceptionWithItem) as context:
            await wrapper.call()
        self.assertEqual(str(context.exception.__cause__), "Test Error")
        self.assertEqual(context.exception.item,
                         {'func': 'failing_func',
                          'args': (),
                          'kwargs': {},
                          'original_function': failing_func})

    async def test_logging_on_exception(self):
        logger = MagicMock()
        error = ValueError("Test Error")

        async def failing_func():
            raise error

        wrapper = CallOrAwait(func=failing_func, logger=logger)
        with self.assertRaises(ExceptionWithItem) as context:
            await wrapper.call()
        logger.error.assert_called_with(
            f"Failed while executing function: {failing_func.__name__}. Error: {error}"
        )
        self.assertEqual({'args': (),
                          'func': failing_func.__name__,
                          'kwargs': {},
                          'original_function': failing_func}, context.exception.item)

    async def test_invalid_function_type(self):
        with self.assertRaises(TypeError):
            CallOrAwait(func="not a function")

    async def test_none_as_func(self):
        func = None
        call = CallOrAwait(func=func)
        self.assertIsNone(call.func)
        self.assertEqual(None, await call.call())

    async def test_invalid_args_type(self):
        with self.assertRaises(TypeError):
            CallOrAwait(func=self.async_func, args="not a tuple")

    async def test_invalid_kwargs_type(self):
        with self.assertRaises(TypeError):
            CallOrAwait(func=self.async_func, kwargs="not a dict")

    async def test_call_with_no_logger(self):
        # Test calling without any logger
        wrapper = CallOrAwait(func=self.async_func, args=(10, 20))
        result = await wrapper.call()
        self.assertEqual(result, 30)

    async def test_call_with_initial_logger(self):
        # Test calling with an initial logger
        logger = MagicMock()
        wrapper = CallOrAwait(func=self.async_func, args=(10, 20), logger=logger)
        result = await wrapper.call()
        self.assertEqual(result, 30)
        logger.error.assert_not_called()

    async def test_call_with_different_logger_on_call(self):
        # Test calling with a different logger than the initial one
        initial_logger = MagicMock()
        override_logger = MagicMock()
        wrapper = CallOrAwait(func=self.async_func, args=(10, 20), logger=initial_logger)
        result = await wrapper.call(logger=override_logger)
        self.assertEqual(result, 30)
        initial_logger.error.assert_not_called()
        override_logger.error.assert_not_called()

    async def test_logging_on_exception_with_initial_logger(self):
        # Test logging on exception with an initial logger
        initial_logger = MagicMock()
        wrapper = CallOrAwait(func=self.failing_func, logger=initial_logger)
        with self.assertRaises(ExceptionWithItem) as context:
            await wrapper.call()
        initial_logger.error.assert_called()
        self.assertEqual(str(context.exception.__cause__), "Test Error")
        self.assertEqual(context.exception.item,
                         {'func': 'failing_func',
                          'args': (),
                          'kwargs': {},
                          'original_function': self.failing_func})

    async def test_logging_on_exception_with_override_logger(self):
        # Test logging on exception with an override logger
        initial_logger = MagicMock()
        override_logger = MagicMock()
        wrapper = CallOrAwait(func=self.failing_func, logger=initial_logger)
        with self.assertRaises(ExceptionWithItem) as context:
            await wrapper.call(logger=override_logger)
        initial_logger.error.assert_not_called()
        override_logger.error.assert_called()
        self.assertEqual(str(context.exception.__cause__), "Test Error")
        self.assertEqual(context.exception.item,
                         {'func': 'failing_func',
                          'args': (),
                          'kwargs': {},
                          'original_function': self.failing_func})


class TestDataToAsyncGenerator(IsolatedAsyncioWrapperTestCase):

    async def async_generator_mock(self, items, raise_exception=False):
        for item in items:
            yield item
        if raise_exception:
            raise Exception("Test Exception")

    async def test_single_item(self):
        item = 42
        async_gen = data_to_async_generator(item)
        results = [i async for i in async_gen]
        self.assertEqual(results, [item])

    async def test_iterable_list(self):
        items = [1, 2, 3]
        async_gen = data_to_async_generator(items)
        results = [i async for i in async_gen]
        self.assertEqual(results, items)

    async def test_iterable_tuple(self):
        items = (1, 2, 3)
        async_gen = data_to_async_generator(items)
        results = [i async for i in async_gen]
        self.assertEqual(results, list(items))

    async def test_iterable_set(self):
        items = {1, 2, 3}
        async_gen = data_to_async_generator(items)
        results = [i async for i in async_gen]
        self.assertEqual(set(results), items)

    async def test_string(self):
        item = "test"
        async_gen = data_to_async_generator(item)
        results = [i async for i in async_gen]
        self.assertEqual(results, [item])

    async def test_bytes(self):
        item = b"test"
        async_gen = data_to_async_generator(item)
        results = [i async for i in async_gen]
        self.assertEqual(results, [item])

    async def test_empty_iterable(self):
        items = []
        async_gen = data_to_async_generator(items)
        results = [i async for i in async_gen]
        self.assertEqual(results, items)

    async def test_async_generator(self):
        async def async_gen():
            for i in range(3):
                yield i
                await asyncio.sleep(0)

        gen = async_gen()
        async_gen = data_to_async_generator(gen)
        results = [i async for i in async_gen]
        self.assertEqual(results, [0, 1, 2])

    async def test_none(self):
        item = None
        async_gen = data_to_async_generator(item)
        results = [i async for i in async_gen]
        self.assertEqual(results, [])

    async def test_exception_handling(self):
        # Create a mock async generator that raises an exception
        mock_gen = self.async_generator_mock([1], raise_exception=True)

        # Call the function and assert the exception
        with self.assertRaises(Exception):
            async for _ in data_to_async_generator(mock_gen):
                pass

    async def test_logging_on_exception(self):
        # Mock logger
        logger = MagicMock()

        # Mock an async generator that raises an exception
        mock_gen = self.async_generator_mock([1], raise_exception=True)

        # Call the function and assert the logger was called
        with self.assertRaises(Exception):
            async for _ in data_to_async_generator(mock_gen, logger=logger):
                pass

        # Assertions
        logger.error.assert_called()

    async def test_raise_with_item(self):
        with self.assertRaises(ExceptionWithItem) as cm:
            raise_with_item(Exception("Original"), ExceptionWithItem, "TestItem")
        self.assertEqual(cm.exception.item, "TestItem")

    async def test_raise_with_item_without_exception_with_item(self):
        with self.assertRaises(Exception) as cm:
            raise_with_item(Exception("Original"), TypeError, "TestItem")
        self.assertNotIsInstance(cm.exception, ExceptionWithItem)

    async def test_raise_with_item_without_exception_class(self):
        with self.assertRaises(Exception) as cm:
            raise_with_item(Exception("Original"), None, "TestItem")
        self.assertNotIsInstance(cm.exception, ExceptionWithItem)

    async def test_data_to_async_generator_with_exception_and_custom_exception_class(self):
        async def failing_async_gen():
            yield 1
            raise Exception("Test Error")

        with self.assertRaises(ExceptionWithItem) as cm:
            [i async for i in data_to_async_generator(failing_async_gen(), exception=ExceptionWithItem)]
        self.assertIsInstance(cm.exception, ExceptionWithItem)
        self.assertIsInstance(cm.exception.item, AsyncGenerator)

    async def test_data_to_async_generator_with_syncgen_exception_and_custom_exception_class(self):
        def failing_async_gen():
            yield 1
            raise Exception("Test Error")

        with self.assertRaises(ExceptionWithItem) as cm:
            [i async for i in data_to_async_generator(failing_async_gen(), exception=ExceptionWithItem)]
        self.assertIsInstance(cm.exception, ExceptionWithItem)
        self.assertIsInstance(cm.exception.item, Generator)

    async def test_data_to_async_generator_with_exception_and_no_custom_exception_class(self):
        async def failing_async_gen():
            yield 1
            raise Exception("Test Error")

        with self.assertRaises(DataGeneratorError) as cm:
            [i async for i in data_to_async_generator(failing_async_gen())]
        self.assertEqual("Test Error", str(cm.exception.__cause__), )


class TestTransformAsyncGenerator(IsolatedAsyncioWrapperTestCase):

    async def sample_async_generator(self) -> AsyncGenerator[int, None]:
        for i in range(3):
            yield i
            await asyncio.sleep(0)

    def sync_transform(self, x: int) -> int:
        return x * 2

    async def async_transform(self, x: int) -> int:
        await asyncio.sleep(0)
        return x * 2

    def generator_transform(self, x: int) -> Generator[int, None, None]:
        yield x * 2

    async def async_generator_transform(self, x: int) -> AsyncGenerator[int, None]:
        await asyncio.sleep(0)
        yield x * 2

    def multiple_values_transform(self, x: int):
        yield x
        yield x * 2

    async def empty_async_generator(self) -> AsyncGenerator[int, None]:
        return
        yield  # This is just to make this a generator

    def error_transform(self, x: int):
        raise ValueError("Transformation Error")

    async def test_sync_transform(self):
        gen = self.sample_async_generator()
        transformed_gen = transform_async_generator(gen, self.sync_transform)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [0, 2, 4])

    async def test_async_transform(self):
        gen = self.sample_async_generator()
        transformed_gen = transform_async_generator(gen, self.async_transform)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [0, 2, 4])

    async def test_generator_transform(self):
        gen = self.sample_async_generator()
        transformed_gen = transform_async_generator(gen, self.generator_transform)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [0, 2, 4])

    async def test_async_generator_transform(self):
        gen = self.sample_async_generator()
        transformed_gen = transform_async_generator(gen, self.async_generator_transform)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [0, 2, 4])

    async def test_async_generator_transform_with_pipe_to_async_generator(self):
        pipe = AsyncMock()
        pipe.get.side_effect = [0, 1, asyncio.CancelledError, 2]
        async_gen = pipe_to_async_generator(pipe)
        transformed_gen = transform_async_generator(async_gen, self.async_generator_transform)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [0, 2])

    async def test_empty_generator(self):
        gen = self.empty_async_generator()
        transformed_gen = transform_async_generator(gen, self.sync_transform)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [])

    @patch.object(CallOrAwait, "call", new_callable=AsyncMock)
    async def test_none_transform_function(self, mock_call_or_await):
        gen = self.sample_async_generator()
        transformed_gen = transform_async_generator(gen, None)
        results = [i async for i in transformed_gen]
        mock_call_or_await.assert_not_called()
        mock_call_or_await.assert_not_awaited()
        self.assertEqual(results, [0, 1, 2])

    async def test_transform_function_yielding_multiple_values(self):
        gen = self.sample_async_generator()
        transformed_gen = transform_async_generator(gen, self.multiple_values_transform)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [0, 0, 1, 2, 2, 4])

    async def test_error_in_transform_function(self):
        gen = self.sample_async_generator()
        with self.assertRaises(ExceptionWithItem):
            async for _ in transform_async_generator(gen, self.error_transform):
                pass

    async def test_generator_not_async_generator(self):
        gen = [0, 1, 2]  # Not an async generator
        with self.assertRaises(TypeError):
            async for _ in transform_async_generator(gen, self.async_transform):
                pass

    async def test_transform_function_none(self):
        gen = self.sample_async_generator()
        transformed_gen = transform_async_generator(gen, None)
        results = [i async for i in transformed_gen]
        self.assertEqual(results, [0, 1, 2])

    async def test_transform_function_not_callable(self):
        gen = self.sample_async_generator()
        with self.assertRaises(TypeError):
            async for _ in transform_async_generator(gen, "not_callable"):
                pass


class TestPutOnConditionFromAsyncGenerator(IsolatedAsyncioWrapperTestCase):
    async def test_normal_operation(self):
        async def test_generator():
            for i in range(3):
                yield i

        destination = AsyncMock()
        await put_on_condition(test_generator(), destination=destination)

        destination.put.assert_has_awaits([call(0), call(1), call(2)])

    async def test_condition_not_met(self):
        async def test_generator():
            for i in range(3):
                yield i

        destination = AsyncMock()
        condition = MagicMock(return_value=False)
        await put_on_condition(test_generator(), destination=destination, on_condition=condition)

        destination.put.assert_not_called()

    async def test_conditional_put_error(self):
        async def test_generator():
            yield 1

        destination = AsyncMock()
        condition = MagicMock(side_effect=Exception("Error in condition"))
        with self.assertRaises(ConditionalPutError):
            await put_on_condition(test_generator(), destination=destination,
                                   on_condition=condition)

    async def test_destination_put_error(self):
        async def test_generator():
            yield 1

        destination = AsyncMock()
        destination.put.side_effect = Exception("Error in put")
        with self.assertRaises(DestinationPutError):
            await put_on_condition(test_generator(), destination=destination)

    async def test_logging(self):
        logger = MagicMock()

        async def test_generator():
            yield 1

        destination = AsyncMock()
        destination.put.side_effect = Exception("Error in put")
        with self.assertRaises(DestinationPutError):
            await put_on_condition(test_generator(), destination=destination, logger=logger)

        logger.error.assert_called()

    async def test_args_kwargs_passed(self):
        async def test_generator():
            yield 1

        destination = AsyncMock()
        await put_on_condition(test_generator(), destination=destination, custom_arg=42)

        destination.put.assert_called_with(1, custom_arg=42)
