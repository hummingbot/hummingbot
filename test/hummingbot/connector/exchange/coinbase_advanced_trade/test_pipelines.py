import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import pipe_to_pipe_connector
from hummingbot.connector.exchange.coinbase_advanced_trade.fittings.pipe_pipe_fitting import PipePipeFitting
from hummingbot.connector.exchange.coinbase_advanced_trade.fittings.stream_pipe_fitting import StreamPipeFitting
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.data_types import HandlerT
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.protocols import PipePutPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.pipeline_base import PipelineBase
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.protocols import StreamMessageIteratorPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import TaskManager


# Define a class for the tests
class TestPipelineBlocks(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self) -> None:
        class MockPipe:
            async def get(self):
                await asyncio.sleep(0.1)  # wait for 100ms before returning a result
                return "message"

            async def snapshot(self):
                await asyncio.sleep(0.5)
                return ("snapshot",)

            def task_done(self):
                pass

        self.source_stream = MagicMock(spec=StreamMessageIteratorPtl[Any])
        self.source_pipe = MockPipe()
        self.destination_pipe = MagicMock(spec=PipePutPtl[Any])

        self.handler: HandlerT = lambda x: x

        self.pipeline_base = PipelineBase(
            source=self.source_pipe,
            handler=self.handler,
            destination=self.destination_pipe,
            connecting_task=pipe_to_pipe_connector
        )
        self.stream_block = StreamPipeFitting(
            source=self.source_stream,
            handler=self.handler,
            destination=self.destination_pipe
        )
        self.pipe_block = PipePipeFitting(
            source=self.source_pipe,
            handler=self.handler,
            destination=self.destination_pipe
        )

    def test_initialization(self) -> None:
        self.assertIsInstance(self.pipeline_base, PipelineBase)
        self.assertIsInstance(self.pipeline_base.task_manager, TaskManager)

        self.assertIsInstance(self.stream_block, StreamPipeFitting)
        self.assertIsInstance(self.stream_block.task_manager, TaskManager)

        self.assertIsInstance(self.pipe_block, PipePipeFitting)
        self.assertIsInstance(self.pipe_block.task_manager, TaskManager)

    async def test_task_execution(self) -> None:
        self.source_pipe.get = MagicMock(return_value=asyncio.Future())
        self.source_pipe.get.return_value.set_result("message")
        self.destination_pipe.put = AsyncMock(return_value=asyncio.Future())
        self.destination_pipe.put.return_value.set_result(None)
        Pipe[int].pipe_snapshot = AsyncMock(return_value=(1, 2, 3))

        await self.pipeline_base.start_task()
        await asyncio.sleep(0.1)  # give the task time to start
        self.assertTrue(self.pipeline_base.is_running())
        await self.pipeline_base.stop_task()
        await asyncio.sleep(0.01)  # give the task time to stop
        self.assertFalse(self.pipeline_base.is_running())

        class InfiniteAsyncIterable:
            async def __call__(self):
                while True:
                    await asyncio.sleep(0)
                    yield "message"

        self.source_stream.iter_messages = InfiniteAsyncIterable()

        await self.stream_block.start_task()
        await asyncio.sleep(0.1)  # give the task time to start
        self.assertTrue(self.stream_block.is_running())
        await self.stream_block.stop_task()
        await asyncio.sleep(0.01)  # give the task time to stop
        self.assertFalse(self.stream_block.is_running())

        await self.pipe_block.start_task()
        await asyncio.sleep(0.01)  # give the task time to start
        self.assertTrue(self.pipe_block.is_running())
        await self.pipe_block.stop_task()
        await asyncio.sleep(0.01)  # give the task time to stop
        self.assertFalse(self.pipe_block.is_running())

    async def test_exception_handling(self) -> None:
        async def put_exception(*args, **kwargs):
            await asyncio.sleep(0.5)
            raise Exception("Test exception")

        self.destination_pipe.put = put_exception

        with patch.object(PipelineBase, "logger") as mock_logger:
            await self.pipeline_base.start_task()
            await asyncio.sleep(0.1)  # give the task time to start
            self.assertTrue(self.pipeline_base.is_running())
            await asyncio.sleep(1)  # give the task time to throw exception
            self.assertFalse(self.pipeline_base.is_running())
            self.assertIsInstance(self.pipeline_base.task_manager._task_exception, Exception)
            mock_logger().error.assert_called_once()

        class InfiniteAsyncIterable:
            async def __call__(self):
                while True:
                    await asyncio.sleep(0.1)
                    yield "message"

        self.source_stream.iter_messages = InfiniteAsyncIterable()

        with patch.object(StreamPipeFitting, "logger") as mock_logger:
            self.destination_pipe.put = put_exception
            await self.stream_block.start_task()
            await asyncio.sleep(0.1)  # give the task time to start
            self.assertTrue(self.stream_block.is_running())
            await asyncio.sleep(1)  # give the task time to throw exception
            self.assertFalse(self.stream_block.is_running())
            self.assertIsInstance(self.stream_block.task_manager._task_exception, Exception)
            mock_logger().error.assert_called_once()

        with patch.object(PipePipeFitting, "logger") as mock_logger:
            await self.pipe_block.start_task()
            await asyncio.sleep(0.1)  # give the task time to start
            self.assertTrue(self.pipe_block.is_running())
            await asyncio.sleep(1)  # give the task time to throw exception
            self.assertFalse(self.pipe_block.is_running())
            self.assertIsInstance(self.pipe_block.task_manager._task_exception, Exception)
            mock_logger().error.assert_called_with("DestinationPutError(, item={'data': 'message', 'item': None})")

    async def test_success_callback(self):
        """Test that the success_callback is called when a task completes successfully."""

        async def successful_task():
            return "Success"

        success_callback = MagicMock()
        task_manager = TaskManager(successful_task, success_callback=success_callback)

        await task_manager.start_task()
        await asyncio.sleep(0.01)  # give the task time to complete

        success_callback.assert_called_once()

    async def test_exception_callback(self):
        """Test that the exception_callback is called when a task throws an exception."""

        async def failing_task():
            raise ValueError("Failure")

        exception_callback = MagicMock()
        task_manager = TaskManager(failing_task, exception_callback=exception_callback)

        await task_manager.start_task()
        await asyncio.sleep(0.1)  # give the task time to throw exception

        exception_callback.assert_called_once()

    async def test_integration(self):
        # Define a source stream that produces a sequence of messages
        class SourceStream:
            async def iter_messages(self):
                for i in range(5):
                    yield f"message {i}"

        # Define a destination pipe that collects messages into a list
        class DestinationPipe:
            def __init__(self):
                self.messages = []

            async def put(self, message, *args, **kwargs):
                self.messages.append(message)

            async def stop(self) -> None:
                pass

        source_stream = SourceStream()
        destination_pipe = DestinationPipe()

        # Create a StreamPipeFitting that reads from the source stream and writes to a pipe
        stream_block = StreamPipeFitting(source=source_stream)

        # Create a PipePipeFitting that reads from the StreamPipeFitting's destination and writes to the destination pipe
        pipe_block = PipePipeFitting(source=stream_block.destination, destination=destination_pipe)

        # Start the blocks
        await pipe_block.start_task()
        await stream_block.start_task()

        # Give the tasks time to run
        await asyncio.sleep(0.5)

        # Check that the destination pipe received the correct messages
        self.assertEqual(destination_pipe.messages, [f"message {i}" for i in range(5)])

        # Stop the blocks
        await stream_block.stop_task()
        await pipe_block.stop_task()
