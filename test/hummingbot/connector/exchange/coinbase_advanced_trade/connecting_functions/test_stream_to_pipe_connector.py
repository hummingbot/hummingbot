import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import MagicMock

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import stream_to_pipe_connector
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.errors import DestinationPutError
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import HandlerT, PipePutPtl
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.errors import PipeFullError


class TestStreamToPipeConnector(IsolatedAsyncioWrapperTestCase):
    class MockStream:
        async def iter_messages(self):
            yield 'message1'
            yield 'message2'

    async def test_normal_operation(self):
        # Mock the source stream, handler, and destination pipe
        source = self.MockStream()
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the source and handler when they are called
        handler.side_effect = ['processed_message1', 'processed_message2']

        # Create TaskManager with the function
        await stream_to_pipe_connector(
            source=source,
            handler=handler,
            destination=destination)

        # Wait for the task to finish
        await asyncio.sleep(0.2)

        # Assert that the handler was called with the correct arguments
        handler.assert_any_call('message1')
        handler.assert_any_call('message2')

        # Assert that the destination's put method was called with the correct arguments
        destination.put.assert_any_call('processed_message1', timeout=0.1)
        destination.put.assert_any_call('processed_message2', timeout=0.1)

        # Assert that the destination's stop method was called
        destination.stop.assert_called()

    async def test_task_cancellation(self):
        class MockStream:
            async def iter_messages(self):
                yield 'message1'
                yield 'message2'
                raise asyncio.CancelledError

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

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

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
            stream_to_pipe_connector(
                source=source,
                handler=handler,
                destination=destination,
                allow_reconnect=False)
        )

        # Check that the task handles the PipeFullError correctly
        with self.assertRaises(DestinationPutError):
            await task

        # Assert that the destination's stop method was called
        destination.stop.assert_called_once()

    async def test_continuous_stream_cancellation(self):
        class ContinuousStream:
            async def iter_messages(self):
                while True:
                    await asyncio.sleep(0)
                    yield 'message'

        # Create a source stream that continuously yields messages
        source = ContinuousStream()
        handler = MagicMock(spec=HandlerT)
        destination = MagicMock(spec=PipePutPtl[Any])

        # Define the behavior of the handler
        handler.return_value = 'processed_message'

        # Start the task
        task = asyncio.create_task(
            stream_to_pipe_connector(
                source=source,
                handler=handler,
                destination=destination)
        )

        # Let the task run for a while, then cancel it
        await asyncio.sleep(0.1)
        task.cancel()
        await asyncio.sleep(0.1)

        # Some cancellation are handled silently by the generators, which
        # terminate so that the data is flushed out
        # Others are raised
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Check that the handler was called with the correct argument
        handler.assert_called_with('message')

        # The exact number of times the handler was called depends on the timing,
        # but it should have been called at least once
        self.assertGreaterEqual(handler.call_count, 1)

        # Assert that the destination's stop method was called
        # destination.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
