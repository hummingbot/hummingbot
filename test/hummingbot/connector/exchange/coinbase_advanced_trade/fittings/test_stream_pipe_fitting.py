import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from hummingbot.connector.exchange.coinbase_advanced_trade.fittings.stream_pipe_fitting import StreamPipeFitting
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe


class MockStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0.1)  # Simulate a stream delay
        return "stream_message"

    async def iter_messages(self):
        yield "stream_message"

    async def start(self):
        pass

    async def stop(self):
        pass


class TestStreamPipeFitting(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Mock stream source and pipe destination
        self.stream_source = MockStream()
        self.destination_pipe = AsyncMock(spec=Pipe)
        self.handler = AsyncMock(return_value="handled_message")  # Mock handler
        self.stream_pipe_fitting = StreamPipeFitting(
            source=self.stream_source,
            handler=self.handler,
            destination=self.destination_pipe
        )

    async def test_initialization(self):
        self.assertIsInstance(self.stream_pipe_fitting, StreamPipeFitting)

    async def test_successful_data_transfer(self):
        # Start the fitting task
        await self.stream_pipe_fitting.start_task()
        await asyncio.sleep(0.2)  # Allow some time for the task to process

        # Verify the handler was called with the correct data
        self.handler.assert_called_once_with("stream_message")

        # Verify the destination put method was called with the handler's output
        self.destination_pipe.put.assert_called_once_with("handled_message", timeout=0.1)

        # Stop the task
        await self.stream_pipe_fitting.stop_task()

    async def test_exception_handling_in_stream(self):
        # Simulate an exception in the stream
        self.stream_source.iter_messages = MagicMock(side_effect=Exception("Test exception"))

        # Patch the logger to verify the logging on exception
        with patch.object(StreamPipeFitting, "_logger") as mock_logger:
            await self.stream_pipe_fitting.start_task()
            await asyncio.sleep(0.2)  # Allow some time for the task to process

            # Verify logger was called with the error
            mock_logger.error.assert_called_once()

            # Verify the task is not running after the exception
            self.assertFalse(self.stream_pipe_fitting.is_running())

        # Stop the task
        await self.stream_pipe_fitting.stop_task()

    async def test_start_and_stop_task(self):
        # Starting the task should set the task_manager to running
        await self.stream_pipe_fitting.start_task()
        self.assertTrue(self.stream_pipe_fitting.is_running())

        # Stopping the task should set the task_manager to not running
        await self.stream_pipe_fitting.stop_task()
        self.assertFalse(self.stream_pipe_fitting.is_running())

    async def test_no_handler_provided(self):
        self.destination_pipe.put = AsyncMock()
        # Create a StreamPipeFitting without a handler
        no_handler_fitting = StreamPipeFitting(
            source=self.stream_source,
            destination=self.destination_pipe
        )

        # Start the fitting task without a handler
        await no_handler_fitting.start_task()
        await asyncio.sleep(0.2)  # Allow some time for the task to process

        # Verify that the destination put method was called with the stream's data
        self.destination_pipe.put.assert_called_once_with("stream_message", timeout=0.1)

        # Stop the task
        await no_handler_fitting.stop_task()


# Run the tests
if __name__ == '__main__':
    unittest.main()
