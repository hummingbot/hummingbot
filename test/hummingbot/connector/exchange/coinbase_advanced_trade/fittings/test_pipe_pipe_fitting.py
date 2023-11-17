import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from test.logger_mixin_for_test import LoggerMixinForTest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.fittings.pipe_pipe_fitting import PipePipeFitting
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe


class TestPipePipeFitting(IsolatedAsyncioWrapperTestCase, LoggerMixinForTest):
    def setUp(self):
        self.source = AsyncMock(spec=Pipe[int]())
        self.destination = AsyncMock(spec=Pipe[int]())
        self.handler = MagicMock()
        self.pipe_pipe_fitting = PipePipeFitting(
            source=self.source,
            handler=self.sync_handler,
            destination=self.destination
        )

        self.set_loggers([self.pipe_pipe_fitting.logger()])

    def sync_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        return item * 10

    async def async_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        self.handler.await_count += 1
        return item * 10

    def generator_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        yield item * 10

    async def asyncgen_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        self.handler.await_count += 1
        yield item * 10

    async def test_initialization(self):
        self.assertIsInstance(self.pipe_pipe_fitting, PipePipeFitting)

    async def test_data_transfer(self):
        self.source = Pipe[int]()
        self.destination = Pipe[int]()
        self.pipe_pipe_fitting = PipePipeFitting(
            source=self.source,
            handler=self.sync_handler,
            destination=self.destination
        )
        # Put a test item in the source pipe
        await self.source.put(1)

        # Start the pipe to pipe fitting task
        self.pipe_pipe_fitting.start_task()

        # Get the item from the destination pipe
        result = await self.destination.get()

        # Check if the handler was called and transformed the data
        self.assertEqual(1, self.handler.call_count)
        self.assertEqual(10, result)

        # Stop the task
        await self.pipe_pipe_fitting.stop_task()

    async def test_exception_handling(self):
        # Simulate an exception in the source get method
        self.source.get = AsyncMock(side_effect=Exception("Test exception"))

        # Start the task and expect the exception callback to be invoked
        with patch.object(PipePipeFitting, "_logger") as mock_logger:
            self.pipe_pipe_fitting.start_task()
            await asyncio.sleep(0.01)  # Give time for the exception to be raised
            mock_logger.error.assert_called_once()

        # Stop the task
        await self.pipe_pipe_fitting.stop_task()

    def test_task_done_functionality(self):
        # Simulate a task_done function in the source pipe
        self.source.task_done = MagicMock()

        # Call task_done on the pipe pipe fitting
        self.pipe_pipe_fitting.task_done()

        # Verify the task_done was called on the source
        self.source.task_done.assert_called_once()

    async def test_get_functionality(self):
        # Simulate a task_done function in the source pipe
        self.source.get = AsyncMock()

        # Call task_done on the pipe pipe fitting
        await self.pipe_pipe_fitting.get()

        # Verify the task_done was called on the source
        self.source.get.assert_called_once()
        self.source.get.assert_awaited_once()

    async def test_snapshot_functionality(self):
        # Simulate a task_done function in the source pipe
        self.source.snapshot = AsyncMock()

        # Call task_done on the pipe pipe fitting
        await self.pipe_pipe_fitting.snapshot()

        # Verify the task_done was called on the source
        self.source.snapshot.assert_called_once()
        self.source.snapshot.assert_awaited_once()

    async def test_start_and_stop_task(self):
        # Starting the task should set the task_manager to running
        self.pipe_pipe_fitting.start_task()
        self.assertTrue(self.pipe_pipe_fitting.is_running())

        # Stopping the task should set the task_manager to not running
        await self.pipe_pipe_fitting.stop_task()
        self.assertFalse(self.pipe_pipe_fitting.is_running())

    async def test_no_handler_provided(self):
        self.source = Pipe[int]()
        self.destination.put = AsyncMock()
        # Create a PipePipeFitting without a handler
        no_handler_fitting = PipePipeFitting(
            source=self.source,
            destination=self.destination
        )

        await self.source.put(1)
        # Start the fitting task without a handler
        no_handler_fitting.start_task()
        await asyncio.sleep(0.1)  # Allow some time for the task to process

        # Verify that the destination put method was called
        self.destination.put.assert_called_once()
        self.destination.put.assert_has_calls([call(1, timeout=0.1)])

        # Stop the task
        await no_handler_fitting.stop_task()


# Run the tests
if __name__ == '__main__':
    unittest.main()
