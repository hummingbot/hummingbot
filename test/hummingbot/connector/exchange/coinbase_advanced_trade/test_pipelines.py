import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.data_types import HandlerT
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.protocols import PipePutPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.connecting_functions import pipe_to_pipe_connector
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.pipe_block import PipeBlock
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.pipeline_block import PipelineBlock
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.pipes_collector import PipesCollector
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.protocols import StreamMessageIteratorPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.stream_block import StreamBlock
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

        self.pipeline_block = PipelineBlock(
            source=self.source_pipe,
            handler=self.handler,
            destination=self.destination_pipe,
            connecting_task=pipe_to_pipe_connector
        )
        self.stream_block = StreamBlock(
            source=self.source_stream,
            handler=self.handler,
            destination=self.destination_pipe
        )
        self.pipe_block = PipeBlock(
            source=self.source_pipe,
            handler=self.handler,
            destination=self.destination_pipe
        )

    async def test_initialization(self) -> None:
        self.assertIsInstance(self.pipeline_block, PipelineBlock)
        self.assertIsInstance(self.pipeline_block.task_manager, TaskManager)

        self.assertIsInstance(self.stream_block, StreamBlock)
        self.assertIsInstance(self.stream_block.task_manager, TaskManager)

        self.assertIsInstance(self.pipe_block, PipeBlock)
        self.assertIsInstance(self.pipe_block.task_manager, TaskManager)

    async def test_task_execution(self) -> None:
        self.source_pipe.get = MagicMock(return_value=asyncio.Future())
        self.source_pipe.get.return_value.set_result("message")
        self.destination_pipe.put = MagicMock(return_value=asyncio.Future())
        self.destination_pipe.put.return_value.set_result(None)
        Pipe[int].pipe_snapshot = AsyncMock(return_value=(1, 2, 3))

        await self.pipeline_block.start_task()
        await asyncio.sleep(0.1)  # give the task time to start
        self.assertTrue(self.pipeline_block.is_running)
        await self.pipeline_block.stop_task()
        await asyncio.sleep(0.01)  # give the task time to stop
        self.assertFalse(self.pipeline_block.is_running)

        class InfiniteAsyncIterable:
            async def __call__(self):
                while True:
                    await asyncio.sleep(0)
                    yield "message"

        self.source_stream.iter_messages = InfiniteAsyncIterable()

        await self.stream_block.start_task()
        await asyncio.sleep(0.1)  # give the task time to start
        self.assertTrue(self.stream_block.is_running)
        await self.stream_block.stop_task()
        await asyncio.sleep(0.01)  # give the task time to stop
        self.assertFalse(self.stream_block.is_running)

        await self.pipe_block.start_task()
        await asyncio.sleep(0.01)  # give the task time to start
        self.assertTrue(self.pipe_block.is_running)
        await self.pipe_block.stop_task()
        await asyncio.sleep(0.01)  # give the task time to stop
        self.assertFalse(self.pipe_block.is_running)

    async def test_exception_handling(self) -> None:
        async def put_exception(*args, **kwargs):
            await asyncio.sleep(0.5)
            raise Exception("Test exception")

        self.destination_pipe.put = put_exception

        with patch.object(PipelineBlock, "logger") as mock_logger:
            await self.pipeline_block.start_task()
            await asyncio.sleep(0.1)  # give the task time to start
            self.assertTrue(self.pipeline_block.is_running)
            await asyncio.sleep(1)  # give the task time to throw exception
            self.assertFalse(self.pipeline_block.is_running)
            self.assertIsInstance(self.pipeline_block.task_manager._task_exception, Exception)
            mock_logger().error.assert_called_once_with(
                f"An error occurred while executing the task in the PipelineBlock:\n"
                f"    {self.pipeline_block.task_manager._task_exception}"
            )

        class InfiniteAsyncIterable:
            async def __call__(self):
                while True:
                    await asyncio.sleep(0.1)
                    yield "message"

        self.source_stream.iter_messages = InfiniteAsyncIterable()

        with patch.object(StreamBlock, "logger") as mock_logger:
            self.destination_pipe.put = put_exception
            await self.stream_block.start_task()
            await asyncio.sleep(0.1)  # give the task time to start
            self.assertTrue(self.stream_block.is_running)
            await asyncio.sleep(1)  # give the task time to throw exception
            self.assertFalse(self.stream_block.is_running)
            self.assertIsInstance(self.stream_block.task_manager._task_exception, Exception)
            mock_logger().error.assert_called_once_with(
                f"An error occurred while executing the task in the StreamBlock:\n"
                f" {self.pipeline_block.task_manager._task_exception}"
            )

        with patch.object(PipeBlock, "logger") as mock_logger:
            await self.pipe_block.start_task()
            await asyncio.sleep(0.1)  # give the task time to start
            self.assertTrue(self.pipe_block.is_running)
            await asyncio.sleep(1)  # give the task time to throw exception
            self.assertFalse(self.pipe_block.is_running)
            self.assertIsInstance(self.pipe_block.task_manager._task_exception, Exception)
            mock_logger().error.assert_called_once_with(
                "An error occurred while executing the task in the PipeBlock:\n"
                f" {self.pipeline_block.task_manager._task_exception}"
            )

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

        # Create a StreamBlock that reads from the source stream and writes to a pipe
        stream_block = StreamBlock(source=source_stream)

        # Create a PipeBlock that reads from the StreamBlock's destination and writes to the destination pipe
        pipe_block = PipeBlock(source=stream_block.destination, destination=destination_pipe)

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


class TestPipesCollector(IsolatedAsyncioWrapperTestCase):

    async def asyncSetUp(self) -> None:
        self.source_pipes: List[Pipe] = [Pipe[str]() for _ in range(3)]
        self.destination_pipe: Pipe[str] = Pipe[str]()

        self.pipes_collector: PipesCollector[str, str] = PipesCollector(
            sources=tuple(self.source_pipes), destination=self.destination_pipe
        )

    async def test_start_task(self) -> None:
        # Mock the start_all_tasks method of the PipeBlock instances
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.start_task = AsyncMock()

        await self.pipes_collector.start_all_tasks()

        # Assert that start_all_tasks was called on each PipeBlock instance
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.start_task.assert_called_once()

    async def test_stop_task(self) -> None:
        # Mock the stop_all_tasks method of the PipeBlock instances
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.stop_task = AsyncMock()

        await self.pipes_collector.stop_all_tasks()

        # Assert that stop_all_tasks was called on each PipeBlock instance
        for pipe_block in self.pipes_collector._pipe_blocks:
            pipe_block.stop_task.assert_called_once()

    async def test_integration(self) -> None:
        class InfiniteAsyncIterable:
            """An async iterable that produces an infinite sequence of messages."""

            def __init__(self, base_message="message"):
                self.base_message = base_message
                self.count = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                message = f"{self.base_message} {self.count}"
                self.count += 1
                return message

        # Prepare an endless stream of messages
        messages = InfiniteAsyncIterable()

        # Feed the messages to the source pipes
        for pipe in self.source_pipes:
            for _ in range(5):  # we only take the first 5 messages for simplicity
                msg = await messages.__anext__()
                await pipe.put(msg)

        # Start the tasks
        await self.pipes_collector.start_all_tasks()
        await asyncio.sleep(0.1)  # give the tasks time to start

        # Check the running status
        self.assertTrue(all(self.pipes_collector.are_running))

        # Stop the tasks
        await self.pipes_collector.stop_all_tasks()
        await asyncio.sleep(0.1)  # give the tasks time to stop

        # Check the running status
        self.assertFalse(any(self.pipes_collector.are_running))

        # Check the messages in the destination pipe
        # In some cases there can be 3 SENTINEL in the destination (one from each source pipe)
        self.assertGreaterEqual(self.destination_pipe.size, len(self.source_pipes) * 5 + 1)
        for pipe in self.source_pipes:
            self.assertEqual(pipe.size, 0)
