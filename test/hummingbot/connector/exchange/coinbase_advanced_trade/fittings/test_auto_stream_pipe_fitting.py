import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, call

from hummingbot.connector.exchange.coinbase_advanced_trade.fittings.auto_stream_pipe_fitting import (
    AutoStreamPipeFitting,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.pipe import Pipe


class MockStream:
    def __aiter__(self):
        return self

    async def __anext__(self):
        await asyncio.sleep(0.1)  # Simulate a stream delay
        return "stream_message"

    async def iter_messages(self):
        for _ in range(5):
            yield "stream_message"

    async def start(self):
        pass

    async def stop(self):
        pass


class TestAutoStreamPipeFitting(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        # Mock stream source, connect, disconnect, and pipe destination
        self.stream_source = MockStream()
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.destination_pipe = AsyncMock(spec=Pipe)
        self.handler = AsyncMock(return_value="handled_message")  # Mock handler
        self.reconnect_interval = 0.5
        self.max_reconnect_attempts = 3
        self.auto_stream_pipe_fitting = AutoStreamPipeFitting(
            source=self.stream_source,
            connect=self.connect,
            disconnect=self.disconnect,
            handler=self.handler,
            destination=self.destination_pipe,
            reconnect_interval=self.reconnect_interval,
            max_reconnect_attempts=self.max_reconnect_attempts
        )

    async def asyncTearDown(self):
        await super().asyncTearDown()
        # Reset mocks
        self.stream_source = None
        self.connect = None
        self.disconnect = None
        self.destination_pipe = None
        self.handler = None
        self.auto_stream_pipe_fitting = None

    async def test_initialization(self):
        self.assertIsInstance(self.auto_stream_pipe_fitting, AutoStreamPipeFitting)

    async def test_successful_data_transfer(self):
        # Start the fitting task
        self.auto_stream_pipe_fitting.start_task()
        await asyncio.sleep(0.2)  # Allow some time for the task to process

        # Verify the handler was called with the correct data
        self.handler.assert_has_calls([
            call('stream_message'),
            call('stream_message'),
            call('stream_message'),
            call('stream_message'),
            call('stream_message')])

        # Verify the destination put method was called with the handler's output
        self.destination_pipe.put.assert_has_calls([
            call('handled_message', timeout=0.1),
            call('handled_message', timeout=0.1),
            call('handled_message', timeout=0.1),
            call('handled_message', timeout=0.1),
            call('handled_message', timeout=0.1)])

        # Stop the task
        await self.auto_stream_pipe_fitting.stop_task()

    async def test_connection_handling(self):
        # Start the fitting task
        self.auto_stream_pipe_fitting.start_task()
        await asyncio.sleep(0.01)  # Allow some time for the task to start

        # Verify connect was called
        self.connect.assert_called_once()

        # Stop the task
        await self.auto_stream_pipe_fitting.stop_task()
        await asyncio.sleep(0.01)  # Allow some time for the task to stop

        # Verify disconnect was called
        self.disconnect.assert_called()

    async def test_exception_handling_in_stream(self):
        async def iter_messages():
            yield "message_pre_exception"
            raise ConnectionError("Test exception")

        # Simulate an exception in the stream
        self.stream_source.iter_messages = iter_messages

        self.auto_stream_pipe_fitting.start_task()
        await asyncio.sleep(0.2)  # Allow some time for the task to process

        self.destination_pipe.put.assert_has_calls([call('handled_message', timeout=0.1)])

        # Verify logger was called with the error
        self.connect.assert_called_once()  # Called at the start of the task
        self.connect.reset_mock()  # Reset to be able to test that it is called once again

        self.disconnect.assert_called_once()
        self.disconnect.reset_mock()  # Reset to be able to test that it is called once again

        # Verify the task is not running after the exception
        self.assertTrue(self.auto_stream_pipe_fitting.is_running())

        # Waiting for the reconnect interval
        await asyncio.sleep(0.6)

        # Verify connect was called again
        self.connect.assert_called_once()

        self.destination_pipe.put.assert_has_calls([
            call('handled_message', timeout=0.1),
            call('handled_message', timeout=0.1), ])
        # Note that the iter_messages is called anew, yielding the same message again,
        # as well as the exception -> disconnect and wait, but this time we stop the task
        # to terminate the test cleanly
        self.disconnect.assert_called_once()

        # Verify the task is not running after the exception
        self.assertTrue(self.auto_stream_pipe_fitting.is_running())

        # Stop the task
        await self.auto_stream_pipe_fitting.stop_task()

    async def test_exception_handling_in_stream_max_attempts(self):
        # Simulate an exception in the stream
        async def iter_messages():
            raise ConnectionError("Test exception")
            yield "message_pre_exception"

        # Simulate an exception in the stream
        self.stream_source.iter_messages = iter_messages

        self.auto_stream_pipe_fitting.start_task()
        await asyncio.sleep(0.2)  # Allow some time for the task to process

        self.destination_pipe.put.assert_not_called()

        # Verify logger was called with the error
        self.connect.assert_called_once()  # Called at the start of the task
        self.connect.reset_mock()  # Reset to be able to test that it is called once again
        self.disconnect.assert_called_once()
        self.disconnect.reset_mock()  # Reset to be able to test that it is called once again

        # Verify the task is not running after the exception
        self.assertTrue(self.auto_stream_pipe_fitting.is_running())

        # Waiting for the maximum reconnect interval
        await asyncio.sleep(self.reconnect_interval * self.max_reconnect_attempts + 0.1)

        # Verify connect was called again
        self.connect.assert_has_calls([call()] * self.max_reconnect_attempts)

        self.destination_pipe.put.assert_not_called()
        # Note that the iter_messages is called anew, yielding the same message again,
        # as well as the exception -> disconnect and wait, but this time we stop the task
        # to terminate the test cleanly
        self.disconnect.assert_has_calls([call()] * self.max_reconnect_attempts)

        # Verify the task is not running after the exception
        self.assertFalse(self.auto_stream_pipe_fitting.is_running())

        # Stop the task - should not raise an exception
        await self.auto_stream_pipe_fitting.stop_task()

    async def test_exception_handling_in_stream_reset_max_attempts(self):
        # Simulate an exception in the stream
        async def iter_messages():
            yield "message_pre_exception"
            raise ConnectionError("Test exception")

        self.stream_source.iter_messages = iter_messages

        self.auto_stream_pipe_fitting.start_task()
        await asyncio.sleep(0.2)  # Allow some time for the task to process

        # Normal operation before the exception
        self.connect.assert_called_once()  # Called at the start of the task
        self.destination_pipe.put.assert_has_calls([call('handled_message', timeout=0.1)])

        # Verify the task is not running after the exception
        self.assertTrue(self.auto_stream_pipe_fitting.is_running())

        # Disconnect from the exception
        self.disconnect.assert_called_once()

        # Verify logger was called with the error
        self.connect.reset_mock()  # Reset to be able to test that it is called once again
        self.destination_pipe.put.reset_mock()  # Reset to be able to test that it is called once again
        self.disconnect.reset_mock()  # Reset to be able to test that it is called once again

        # Waiting for the 2x maximum reconnect interval - Because a successful message is sent
        # after the exception, the reconnect counter is reset, thus creating a endless loop
        await asyncio.sleep(2 * (self.reconnect_interval * self.max_reconnect_attempts))

        # Verify connect was called a number of times equal to the number of intervals during the sleep
        self.connect.assert_has_calls([call()] * self.max_reconnect_attempts * 2)

        # Note that the iter_messages is called anew, yielding the same message again,
        # as well as the exception -> disconnect and wait
        # After each exception, a successful message is sent, thus resetting the reconnect counter
        self.destination_pipe.put.assert_has_calls([call('handled_message', timeout=0.1)] * self.max_reconnect_attempts * 2)
        self.disconnect.assert_has_calls([call()] * self.max_reconnect_attempts * 2)

        # Verify the task is still running after each exception
        self.assertTrue(self.auto_stream_pipe_fitting.is_running())

        # This is an endless loop: we must stop the task
        await self.auto_stream_pipe_fitting.stop_task()

    async def test_connection_error_handling_in_stream_reset_max_attempts(self):
        # Simulate an exception in the stream
        async def iter_messages():
            yield "message_pre_exception"
            raise ConnectionError("Test exception")

        self.stream_source.iter_messages = iter_messages

        self.auto_stream_pipe_fitting.start_task()
        await asyncio.sleep(0.1)  # Allow one round on the event loop to start the task

        # Normal operation before the exception
        self.connect.assert_called_once()  # Called at the start of the task
        self.destination_pipe.put.assert_has_calls([call('handled_message', timeout=0.1)])

        # Verify the task is not running after the exception
        self.assertTrue(self.auto_stream_pipe_fitting.is_running())

        # Disconnect from the exception
        self.disconnect.assert_called_once()

        self.connect.reset_mock()  # Reset to be able to test that it is called once again
        self.destination_pipe.put.reset_mock()  # Reset to be able to test that it is called once again
        self.disconnect.reset_mock()  # Reset to be able to test that it is called once again

        # The reconnect logic disconnects then await on the reconnect_interval
        await asyncio.sleep(self.reconnect_interval * 0.5)
        self.assertEqual(0, self.connect.call_count)

        await asyncio.sleep(self.reconnect_interval * 0.5)
        self.assertEqual(1, self.connect.call_count)

        await asyncio.sleep(self.reconnect_interval * (self.max_reconnect_attempts - 1))
        # Verify connect was called a number of times equal to the number of intervals during the sleep
        self.assertTrue(self.connect.call_count >= self.max_reconnect_attempts)

        # Note that the iter_messages is called anew, yielding the same message again,
        # as well as the exception -> disconnect and wait
        # After each exception, a successful message is sent, thus resetting the reconnect counter
        self.assertTrue(self.destination_pipe.put.call_count >= self.max_reconnect_attempts)
        self.assertTrue(self.disconnect.call_count >= self.max_reconnect_attempts)

        # Verify the task is still running after each exception
        self.assertTrue(self.auto_stream_pipe_fitting.is_running())

        # This is an endless loop: we must stop the task
        await self.auto_stream_pipe_fitting.stop_task()


# Run the tests
if __name__ == '__main__':
    unittest.main()
