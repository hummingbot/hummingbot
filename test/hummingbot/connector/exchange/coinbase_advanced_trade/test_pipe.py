import asyncio
from asyncio import QueueFull
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import (
    SENTINEL,
    HandlerT,
    Pipe,
    PipeAsyncIterator,
    PipeFullError,
    PipeGetPtl,
    PipePutPtl,
    PipeSentinelError,
    PipeStoppedError,
    _get_pipe_put_operation_for_handler,
    pipe_to_async_generator,
    pipe_to_multipipe_distributor,
    pipe_to_pipe_connector,
    stream_to_pipe_connector,
)


class TestPipe(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        self.pipe = Pipe[int](maxsize=2)

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

    async def test_put(self):
        await self.pipe.put(1)
        self.assertEqual(await self.pipe.pipe.get(), 1)

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
        self.assertEqual((SENTINEL,), await self.pipe.pipe_snapshot(self.pipe))
        print(self.pipe.pipe.qsize())

    async def test_snapshot(self):
        items = (1, 2)
        for item in items:
            await self.pipe.put(item)
        snapshot = await Pipe.pipe_snapshot(self.pipe)
        self.assertTupleEqual(items, snapshot)
        self.assertTrue(self.pipe.empty)

    async def test_continual_put_in_queue_gets_full_and_stopped(self):
        asyncio.create_task(self.continual_put_in_queue())
        await asyncio.sleep(0.5)  # allow queue to get full
        await self.pipe.stop()
        self.assertTrue(self.pipe.is_stopped)
        self.assertEqual(2, self.pipe.size)
        self.assertEqual((0, 1), await self.pipe.pipe_snapshot(self.pipe))

    async def test_put_into_stopped_pipe_raises_error(self):
        await self.pipe.stop()
        with self.assertRaises(PipeStoppedError):
            await self.pipe.put(1)

    async def test_put_handles_queue_full(self):
        await self.pipe.put(1)
        await self.pipe.put(2)

        with patch.object(Pipe, "logger") as mock_logger:
            with self.assertRaises(PipeFullError):
                await self.pipe.put(3, max_wait_time_per_retry=0.5)  # This should raise an error after max retries
        mock_logger.assert_called()

    async def test_task_done_and_join(self):
        await self.pipe.put(1)
        await self.pipe.get()
        self.pipe.task_done()
        join_task = asyncio.create_task(self.pipe.join())
        await asyncio.sleep(0.1)  # Give the join task some time to run
        self.assertTrue(join_task.done())

    async def test_sentinel_ize(self):
        items = (1, 2, 3)
        sentinelized_items = self.pipe.sentinel_ize(items)
        self.assertEqual(sentinelized_items, (1, 2, 3, SENTINEL))

    async def test_sentinel_ize_with_existing_sentinel(self):
        items = (1, 2, SENTINEL, 3)
        sentinelized_items = self.pipe.sentinel_ize(items)
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


class TestPipeRelatedFunctions(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):

    async def asyncSetUp(self):
        self.pipe = Pipe[int](maxsize=5)
        self.level = 1
        self.set_loggers([self.pipe.logger()])

    async def test_queue_to_async_generator_consecutively(self):
        items = [1, 2, 3]
        for item in items:
            await self.pipe.put(item)
        await self.pipe._put_sentinel()
        async for item in pipe_to_async_generator(self.pipe):
            self.assertEqual(item, items.pop(0))
        self.assertEqual(0, len(items))

    async def test_queue_to_async_generator(self):
        items = [1, 2, 3, 4, 5]
        for item in items:
            await self.pipe.put(item)

        # Start consuming items from the queue in a separate task
        async def consume_items():
            consumed_items = []
            async for item in pipe_to_async_generator(self.pipe):
                consumed_items.append(item)
            return consumed_items

        consume_task = asyncio.create_task(consume_items())

        # Wait a bit to allow the consumer to start processing items
        await asyncio.sleep(0.1)

        # Stop the queue while the consumer is still running
        await self.pipe.stop()

        # Wait for the consumer to finish processing all items
        consumed_items = await consume_task

        # Check that all items were consumed before the queue was stopped
        self.assertEqual(consumed_items, items)

    async def test_max_retries_raises_error(self):
        # Fill the queue
        for i in range(5):
            await self.pipe.put(i)

        # Try to put another item into the full queue
        with self.assertRaises(PipeFullError):
            await self.pipe.put(5, wait_time=0.01, max_retries=3)
        self.assertTrue(self.is_partially_logged("DEBUG", "Pipe is full"))
        self.assertTrue(self.is_partially_logged("ERROR", "Failed to put item after"))

    async def test_zero_wait_time(self):
        # Fill the queue
        for i in range(5):
            await self.pipe.put(i)

        # Try to put another item into the full queue
        with self.assertRaises(PipeFullError):
            await self.pipe.put(5, wait_time=0, max_retries=3)
        self.assertTrue(self.is_partially_logged("DEBUG", "Pipe is full"))
        self.assertTrue(self.is_partially_logged("ERROR", "Failed to put item after"))

    async def test_queue_to_async_generator_with_endless_feeder_and_consumer(self):
        # Start an endless feeder task that puts items into the queue
        async def feeder():
            i = 0
            while not self.pipe.is_stopped:
                await self.pipe.put(i)
                i += 1

        feeder_task = asyncio.create_task(feeder())

        # Start an endless consumer task that gets items from the queue
        async def consumer():
            consumed_items = []
            async for item in pipe_to_async_generator(self.pipe):
                consumed_items.append(item)
            return consumed_items

        consumer_task = asyncio.create_task(consumer())

        # Let the feeder and consumer run for a bit
        await asyncio.sleep(0.5)

        # Stop the queue, which will also stop the feeder and consumer
        await self.pipe.stop()

        # Wait for the feeder and consumer to finish
        await feeder_task
        consumed_items = await consumer_task

        # Check that the consumer consumed the correct items
        self.assertEqual(consumed_items, list(range(len(consumed_items))))


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


class TestHandler(IsolatedAsyncioWrapperTestCase):
    async def test_get_pipe_put_operation_for_handler(self):
        destination = AsyncMock()

        # Regular function
        def handler1(m):
            return m * 2

        put_operation = _get_pipe_put_operation_for_handler(handler=handler1, destination=destination)
        await put_operation(5)
        destination.put.assert_called_once_with(10)

        # Coroutine function
        async def handler2(m):
            return m * 3

        put_operation = _get_pipe_put_operation_for_handler(handler=handler2, destination=destination)
        await put_operation(5)
        destination.put.assert_called_with(15)

        # Generator function
        def handler3(m):
            for i in range(m):
                yield i

        destination.reset_mock()
        put_operation = _get_pipe_put_operation_for_handler(handler=handler3, destination=destination)
        await put_operation(5)
        assert destination.put.call_count == 5

        # Async generator function
        async def handler4(m):
            for i in range(m):
                yield i

        destination.reset_mock()
        put_operation = _get_pipe_put_operation_for_handler(handler=handler4, destination=destination)
        await put_operation(5)
        assert destination.put.call_count == 5


class TestGetPutOperationForHandler(IsolatedAsyncioWrapperTestCase):
    async def test_handler_is_none(self):
        destination = MagicMock(spec=PipePutPtl)

        put_operation = _get_pipe_put_operation_for_handler(handler=None, destination=destination)
        await put_operation('test message')
        self.assertEqual('test message', destination.put.call_args[0][0])

    async def test_handler_raises_exception(self):
        async def handler_raises_exception(message):
            raise Exception('test')

        put_operation = _get_pipe_put_operation_for_handler(handler=handler_raises_exception, destination=MagicMock())
        with self.assertRaises(Exception):
            await put_operation('test message')

    async def test_destination_pipe_is_full(self):
        destination = MagicMock(spec=PipePutPtl)
        destination.put.side_effect = QueueFull()

        put_operation = _get_pipe_put_operation_for_handler(handler=lambda m: m, destination=destination)
        with self.assertRaises(QueueFull):
            await put_operation('test message')

    async def test_handler_yields_no_values(self):
        async def async_gen_handler(message):
            if False:  # This async generator will yield no values
                yield 'test'

        destination = MagicMock(spec=PipePutPtl)
        put_operation = _get_pipe_put_operation_for_handler(handler=async_gen_handler, destination=destination)
        await put_operation('test message')  # This should do nothing

        destination.put.assert_not_called()  # Assert that nothing was put to the destination pipe


class TestPipeConnectingTask(IsolatedAsyncioWrapperTestCase):

    async def test_normal_operation(self):
        # Mock the source, handler, and destination objects
        source = MagicMock(spec=PipeGetPtl[Any])
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        source.get.side_effect = ['message1', 'message2', SENTINEL]
        handler.side_effect = ['processed_message1', 'processed_message2']

        # Call the function
        await pipe_to_pipe_connector(source=source, handler=handler, destination=destination)

        # Assert that the source's get method was called thrice
        self.assertEqual(source.get.call_count, 3)

        # Assert that the handler was called with the correct arguments
        handler.assert_any_call('message1')
        handler.assert_any_call('message2')

        # Assert that the destination's put method was called with the correct arguments
        destination.put.assert_any_call('processed_message1', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)
        destination.put.assert_any_call('processed_message2', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_task_cancellation(self):
        # Simulates a source with ('message1', 'message2', 'message3', 'message4')
        # with a task cancellation occuring after the second message is processed
        # The call to snapshot(0 grabs the remaining messages in the source queue
        # that may or may not contain the sentinel. process message3, message4
        # and stops the downstream Pipe

        async def mock_snapshot():
            return ('message3', 'message4')

        # Mock the source, handler, and destination objects
        source = MagicMock(spec=PipeGetPtl[Any])
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        source.snapshot = mock_snapshot
        source.get.side_effect = ['message1', 'message2', asyncio.CancelledError]
        handler.side_effect = ['processed_message1', 'processed_message2', 'processed_message3', 'processed_message4']

        # Call the function
        with self.assertRaises(asyncio.CancelledError):
            await pipe_to_pipe_connector(source=source, handler=handler, destination=destination)

        # Assert that the source's get method was called thrice
        self.assertEqual(3, source.get.call_count, 3)

        # Assert that the handler was called with the correct arguments
        handler.assert_any_call('message1')
        handler.assert_any_call('message2')
        handler.assert_any_call('message3')
        handler.assert_any_call('message4')

        # Assert that the destination's put method was called with the correct arguments
        destination.put.assert_any_call('processed_message1', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)
        destination.put.assert_any_call('processed_message2', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)
        destination.put.assert_any_call('processed_message3')
        destination.put.assert_any_call('processed_message4')

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_task_cancellation_and_destination_full(self):
        # Simulates a source with ('message1', 'message2', 'message3', 'message4')
        # with a task cancellation occurring after the second message is processed
        # The call to snapshot(0 grabs the remaining messages in the source queue
        # that may or may not contain the sentinel. process message3, message4
        # and stops the downstream Pipe

        async def mock_snapshot():
            return ('message3', 'message4')

        # Mock the source, handler, and destination objects
        source = MagicMock(spec=PipeGetPtl[Any])
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        source.snapshot = mock_snapshot
        source.get.side_effect = ['message1', 'message2', asyncio.CancelledError]
        handler.side_effect = ['processed_message1', 'processed_message2', 'processed_message3', 'processed_message4']
        destination.put.side_effect = [None, None, PipeFullError()]

        # Call the function
        with self.assertRaises(asyncio.CancelledError):
            await pipe_to_pipe_connector(source=source, handler=handler, destination=destination)

        # Assert that the source's get method was called thrice
        self.assertEqual(3, source.get.call_count, 3)

        # Assert that the handler was called with the correct arguments
        handler.assert_any_call('message1')
        handler.assert_any_call('message2')
        # Message is handled, but ultimately not put in destination
        handler.assert_any_call('message3')
        # Message will not be handled, the QueueFull breaks the messages iteration
        with self.assertRaises(AssertionError):
            handler.assert_any_call('message4')

        # Assert that the destination's put method was called with the correct arguments
        destination.put.assert_any_call('processed_message1', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)
        destination.put.assert_any_call('processed_message2', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)
        # Message is sent to the pipe that raises a QueueFull
        destination.put.assert_any_call('processed_message3')
        # The QueueFull breaks the messages iteration, so message4 is not put in destination
        with self.assertRaises(AssertionError):
            destination.put.assert_any_call('processed_message4')

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_handler_is_generator(self):
        def handler_generator(message):
            yield f'processed_{message}'

        source = MagicMock(spec=PipeGetPtl[Any])
        destination = MagicMock(spec=PipePutPtl[Any])

        source.get.side_effect = ['message1', 'message2', SENTINEL]

        await pipe_to_pipe_connector(source=source, handler=handler_generator, destination=destination)

        # Assert that the source's get method was called thrice
        self.assertEqual(3, source.get.call_count)
        self.assertEqual(3, source.task_done.call_count)
        self.assertEqual(0, source.snapshot.call_count)

        # Assert that the destination's put method was called with the correct arguments
        # We do not put the SENTINEL in the destination pipe
        self.assertEqual(2, destination.put.call_count)
        destination.put.assert_any_call('processed_message1', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)
        destination.put.assert_any_call('processed_message2', wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_handler_raises_exception(self):
        async def mock_snapshot():
            return ('message1', 'message2', SENTINEL)

        def handler_raises_exception(message):
            raise ValueError('test')

        source = MagicMock(spec=PipeGetPtl[Any])
        destination = MagicMock(spec=PipePutPtl[Any])

        source.snapshot = mock_snapshot
        source.get.side_effect = ['message1', 'message2', SENTINEL]

        with self.assertRaises(ValueError):
            await pipe_to_pipe_connector(source=source, handler=handler_raises_exception, destination=destination)


class TestStreamToPipeConnector(IsolatedAsyncioWrapperTestCase):
    class MockStream:
        async def iter_messages(self):
            yield 'message1'
            yield 'message2'

    async def test_normal_operation(self):
        class MockStream:
            async def iter_messages(self):
                yield 'message1'
                yield 'message2'

        # Mock the source stream, handler, and destination pipe
        source = MockStream()
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        handler.side_effect = ['processed_message1', 'processed_message2']

        # Create TaskManager with the function
        await stream_to_pipe_connector(source=source, handler=handler, destination=destination)

        # Wait for the task to finish
        await asyncio.sleep(0.2)

        # Assert that the handler was called with the correct arguments
        handler.assert_any_call('message1')
        handler.assert_any_call('message2')

        # Assert that the destination's put method was called with the correct arguments
        destination.put.assert_any_call('processed_message1')
        destination.put.assert_any_call('processed_message2')

        # Assert that the destination's stop method was called
        destination.stop.assert_not_called()

# TODO: This may not be a valid/necessary test
#    async def test_task_cancellation(self):
#        class MockStream:
#            async def iter_messages(self):
#                yield 'message1'
#                yield 'message2'
#                raise asyncio.CancelledError
#
#        # Mock the source stream, handler, and destination pipe
#        source = MockStream()
#        handler = MagicMock(spec=HandlerT)
#        destination = MagicMock(spec=PipePutPtl[Any])
#
#        # Define the behavior of the source and handler when they are called
#        handler.side_effect = ['processed_message1', 'processed_message2']
#
#        # Create TaskManager with the function
#        await stream_to_pipe_connector(source=source, handler=handler, destination=destination)
#
#        # Wait for the task to finish
#        await asyncio.sleep(0.2)
#
#        # Assert that the destination's stop method was called
#        destination.stop.assert_called_once()

    async def test_unexpected_error(self):
        class MockStream:
            async def iter_messages(self):
                yield 'message1'
                yield 'message2'
                raise ValueError("Unexpected error")

        # Mock the source stream, handler, and destination pipe
        source = MockStream()
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        handler.side_effect = ['processed_message1', 'processed_message2']

        # Create TaskManager with the function
        with self.assertRaises(ValueError):
            await stream_to_pipe_connector(source=source, handler=handler, destination=destination)
            # Wait for the task to finish
            await asyncio.sleep(0.2)

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_handler_exception(self):
        # Mock the source stream, handler, and destination pipe
        source = self.MockStream()
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        handler.side_effect = ['processed_message1', Exception('Test exception'), 'processed_message3',
                               'processed_message4']

        # Start the task
        task = asyncio.create_task(
            stream_to_pipe_connector(source=source, handler=handler, destination=destination)
        )

        # Check that the task raises the exception from the handler
        with self.assertRaises(Exception, msg='Test exception'):
            await task

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_full_destination_pipe(self):
        class MockStream:
            async def iter_messages(self):
                yield 'message1'
                yield 'message2'
                yield 'message3'
                yield 'message4'
                yield 'message5'

        # Mock the source stream, handler, and destination pipe
        source = MockStream()
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        handler.side_effect = ['processed_message1', 'processed_message2', 'processed_message3', 'processed_message4']
        destination.put.side_effect = [None, None, PipeFullError, PipeFullError, PipeFullError, PipeFullError,
                                       PipeFullError, PipeFullError]

        # Start the task
        task = asyncio.create_task(
            stream_to_pipe_connector(source=source, handler=handler, destination=destination)
        )

        # Check that the task handles the PipeFullError correctly
        with self.assertRaises(PipeFullError):
            await task

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_continuous_stream_cancellation(self):
        class ContinuousStream:
            async def iter_messages(self):
                while True:
                    # It seems crucial to release control to the event loop here (with await asyncio.sleep(0))
                    try:
                        await asyncio.sleep(0)
                        yield 'message'
                    except asyncio.CancelledError:
                        raise

        # Create a source stream that continuously yields messages
        source = ContinuousStream()
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the handler
        handler.return_value = 'processed_message'

        # Start the task
        task = asyncio.create_task(
            stream_to_pipe_connector(source=source, handler=handler, destination=destination)
        )

        # Let the task run for a while, then cancel it
        await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.sleep(0.1)

        # Check that the task was cancelled
        with self.assertRaises(asyncio.CancelledError):
            await task

        # Check that the handler was called with the correct argument
        handler.assert_called_with('message')

        # The exact number of times the handler was called depends on the timing,
        # but it should have been called at least once
        self.assertGreaterEqual(handler.call_count, 1)

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()


class TestPipeToMultiPipeDistributor(IsolatedAsyncioWrapperTestCase):
    class MockPipe:
        def __init__(self, items):
            self._items = items

        async def get(self):
            return self._items.pop(0) if self._items else SENTINEL

        async def put(self, item):
            self._items.append(item)

        def task_done(self):
            pass

        async def stop(self):
            self._items.append(SENTINEL)

    class MockHandler:
        def __init__(self, transform):
            self._transform = transform

        def __call__(self, item):
            return self._transform(item)

    async def test_normal_operation_one_handler(self):
        # Setup
        source = self.MockPipe(['message1', 'message2'])
        destinations = [self.MockPipe([]), self.MockPipe([])]
        handler = self.MockHandler(lambda x: f'processed_{x}')

        # Run
        await pipe_to_multipipe_distributor(source=source, handlers=handler, destinations=destinations)

        # Check
        self.assertEqual(destinations[0]._items, ['processed_message1', 'processed_message2', SENTINEL])
        self.assertEqual(destinations[1]._items, ['processed_message1', 'processed_message2', SENTINEL])

    async def test_normal_operation_multiple_handlers(self):
        # Setup
        source = self.MockPipe(['message1', 'message2'])
        destinations = [self.MockPipe([]), self.MockPipe([])]
        handlers = [
            self.MockHandler(lambda x: f'processed_{x}'),
            self.MockHandler(lambda x: f'double_processed_{x}'),
        ]

        # Run
        await pipe_to_multipipe_distributor(source=source, handlers=handlers, destinations=destinations)

        # Check
        self.assertEqual(destinations[0]._items, ['processed_message1', 'processed_message2', SENTINEL])
        self.assertEqual(destinations[1]._items, ['double_processed_message1', 'double_processed_message2', SENTINEL])

    async def test_incorrect_number_of_handlers(self):
        # Setup
        source = self.MockPipe(['message1', 'message2'])
        destinations = [self.MockPipe([]), self.MockPipe([]), self.MockPipe([])]
        handlers = [
            self.MockHandler(lambda x: f'processed_{x}'),
            self.MockHandler(lambda x: f'double_processed_{x}'),
        ]

        # Run and check
        with self.assertRaises(ValueError):
            await pipe_to_multipipe_distributor(source=source, handlers=handlers, destinations=destinations)

    async def test_sentinel_handling(self):
        # Setup
        source = self.MockPipe([])
        destinations = [self.MockPipe([]), self.MockPipe([])]
        handler = self.MockHandler(lambda x: f'processed_{x}')

        # Run
        await pipe_to_multipipe_distributor(source=source, handlers=handler, destinations=destinations)

        # Check
        self.assertEqual(destinations[0]._items, [SENTINEL])
        self.assertEqual(destinations[1]._items, [SENTINEL])
