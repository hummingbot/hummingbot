import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import pipe_to_pipe_connector
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.data_types import HandlerT
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.protocols import PipePutPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.pipeline.pipeline_base import PipelineBase
from hummingbot.connector.exchange.coinbase_advanced_trade.task_manager import TaskManager


# Define a class for the tests
class TestPipelineBase(IsolatedAsyncioWrapperTestCase):
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

        self.source_pipe = MockPipe()
        self.destination_pipe = MagicMock(spec=PipePutPtl[Any])

        self.handler: HandlerT = lambda x: x

        self.pipeline_base = PipelineBase(
            source=self.source_pipe,
            handler=self.handler,
            destination=self.destination_pipe,
            connecting_task=pipe_to_pipe_connector
        )

    def test_initialization(self) -> None:
        self.assertIsInstance(self.pipeline_base, PipelineBase)
        self.assertIsInstance(self.pipeline_base.task_manager, TaskManager)

    async def test_task_execution(self) -> None:
        async def mock_get():
            # This allows us to test that the task is running - endless get messages
            return "message"

        self.source_pipe.get = mock_get
        self.destination_pipe.put = AsyncMock()

        self.pipeline_base.start_task()

        await asyncio.sleep(0.2)

        self.assertTrue(self.pipeline_base.is_running())

        await self.pipeline_base.stop_task()
        await asyncio.sleep(0.1)

        self.assertFalse(self.pipeline_base.is_running())
        self.destination_pipe.put.assert_called()
        self.destination_pipe.put.assert_called_with('message', timeout=0.1)

    async def test_exception_handling(self) -> None:
        async def put_exception(*args, **kwargs):
            await asyncio.sleep(0.5)
            raise Exception("Test exception")

        self.destination_pipe.put = put_exception

        with patch.object(PipelineBase, "logger") as mock_logger:
            self.pipeline_base.start_task()
            await asyncio.sleep(0.1)  # give the task time to start
            self.assertTrue(self.pipeline_base.is_running())
            await asyncio.sleep(1)  # give the task time to throw exception
            self.assertFalse(self.pipeline_base.is_running())
            self.assertIsInstance(self.pipeline_base.task_manager._task_exception, Exception)
            mock_logger().error.assert_called_once()

    async def test_success_callback(self):
        """Test that the success_callback is called when a task completes successfully."""

        async def successful_task():
            return "Success"

        success_callback = MagicMock()
        task_manager = TaskManager(successful_task, success_callback=success_callback)

        task_manager.start_task()
        await asyncio.sleep(0.01)  # give the task time to complete

        success_callback.assert_called_once()

    async def test_exception_callback(self):
        """Test that the exception_callback is called when a task throws an exception."""

        async def failing_task():
            raise ValueError("Failure")

        exception_callback = MagicMock()
        task_manager = TaskManager(failing_task, exception_callback=exception_callback)

        task_manager.start_task()
        await asyncio.sleep(0.1)  # give the task time to throw exception

        exception_callback.assert_called_once()
