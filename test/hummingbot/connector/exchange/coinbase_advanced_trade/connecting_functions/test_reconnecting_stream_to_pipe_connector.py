import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import (
    reconnecting_stream_to_pipe_connector,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import Pipe


class TestReconnectingStreamToPipeConnector(IsolatedAsyncioWrapperTestCase):
    class MockStream:
        async def iter_messages(self):
            yield 1
            yield 2
            yield 3

    async def asyncSetUp(self):
        self.source = self.MockStream()
        self.handler = AsyncMock()
        self.destination = MagicMock(spec=Pipe)
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.logger = MagicMock()

    def sync_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        return item * 2

    async def async_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        self.handler.await_count += 1
        return item * 2

    def generator_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        yield item * 2

    async def asyncgen_handler(self, item: Any) -> Any:
        self.handler.call_count += 1
        self.handler.await_count += 1
        yield item * 2

    async def test_successful_connection_and_data_transfer(self):
        self.destination.put = AsyncMock()

        await reconnecting_stream_to_pipe_connector(
            source=self.source,
            handler=self.sync_handler,
            destination=self.destination,
            connect=self.connect,
            disconnect=self.disconnect,
            reconnect_interval=0.1,
            logger=self.logger)

        # Verify that connect and disconnect were called
        self.connect.assert_awaited_once()
        self.disconnect.assert_awaited_once()

        # Check that the handler processed the items correctly
        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1),
            call(4, timeout=0.1),
            call(6, timeout=0.1)])

    async def test_successful_connection_and_data_transfer_async_handler(self):
        self.destination.put = AsyncMock()

        await reconnecting_stream_to_pipe_connector(
            source=self.source,
            handler=self.async_handler,
            destination=self.destination,
            connect=self.connect,
            disconnect=self.disconnect,
            reconnect_interval=0.1,
            logger=self.logger)

        # Verify that connect and disconnect were called
        self.connect.assert_awaited_once()
        self.disconnect.assert_awaited_once()

        # Check that the handler processed the items correctly
        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1),
            call(4, timeout=0.1),
            call(6, timeout=0.1)])

        # Check that the handler was called with the correct arguments
        self.assertEqual(self.handler.await_count, 3)

    async def test_successful_connection_and_data_transfer_generator_handler(self):
        self.destination.put = AsyncMock()

        await reconnecting_stream_to_pipe_connector(
            source=self.source,
            handler=self.generator_handler,
            destination=self.destination,
            connect=self.connect,
            disconnect=self.disconnect,
            reconnect_interval=0.1,
            logger=self.logger)

        # Verify that connect and disconnect were called
        self.connect.assert_awaited_once()
        self.disconnect.assert_awaited_once()

        # Check that the handler processed the items correctly
        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1),
            call(4, timeout=0.1),
            call(6, timeout=0.1)])

        # Check that the handler was called with the correct arguments
        self.assertEqual(self.handler.call_count, 3)

    async def test_successful_connection_and_data_transfer_asyncgen_handler(self):
        self.destination.put = AsyncMock()

        await reconnecting_stream_to_pipe_connector(
            source=self.source,
            handler=self.asyncgen_handler,
            destination=self.destination,
            connect=self.connect,
            disconnect=self.disconnect,
            reconnect_interval=0.1,
            logger=self.logger)

        # Verify that connect and disconnect were called
        self.connect.assert_awaited_once()
        self.disconnect.assert_awaited_once()

        # Check that the handler processed the items correctly
        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1),
            call(4, timeout=0.1),
            call(6, timeout=0.1)])

        # Check that the handler was called with the correct arguments
        self.assertEqual(self.handler.await_count, 3)

    async def test_handling_reconnection(self):
        class MockStream:
            def __init__(self):
                self.reconnected = False

            async def iter_messages(self):
                yield 1
                if not self.reconnected:
                    self.reconnected = True
                    raise ConnectionError("Disconnected")
                yield 2

        self.source = MockStream()
        self.destination.put = AsyncMock()

        await reconnecting_stream_to_pipe_connector(
            source=self.source,
            handler=self.asyncgen_handler,
            destination=self.destination,
            connect=self.connect,
            disconnect=self.disconnect,
            max_reconnect_attempts=2,
            reconnect_interval=1,
            logger=self.logger)

        # Verify reconnection attempts
        self.assertEqual(self.connect.await_count, 2)
        self.assertEqual(self.disconnect.await_count, 2)

        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1),
            # When reconnected, the test starts the iter_message() anew, thus 1 is sent again
            call(2, timeout=0.1),
            call(4, timeout=0.1)])

    async def test_handling_max_reconnection(self):
        class MockStream:
            def __init__(self):
                self.reconnected = False

            async def iter_messages(self):
                raise ConnectionError("Disconnected")
                yield 1

        self.source = MockStream()
        self.destination.put = AsyncMock()

        with self.assertRaises(ConnectionError):
            await reconnecting_stream_to_pipe_connector(
                source=self.source,
                handler=self.asyncgen_handler,
                destination=self.destination,
                connect=self.connect,
                disconnect=self.disconnect,
                max_reconnect_attempts=2,
                reconnect_interval=0.1,
                logger=self.logger)

        # Verify reconnection attempts initial and final and 2 retries
        self.assertEqual(3, self.connect.await_count, )
        self.assertEqual(3, self.disconnect.await_count, )

        self.destination.put.assert_not_called()

    async def test_handling_reconnection_with_reconnect_exception_type(self):
        class MockStream:
            def __init__(self):
                self.reconnected = False

            async def iter_messages(self):
                yield 1
                if not self.reconnected:
                    self.reconnected = True
                    raise ValueError("Disconnected")
                yield 2

        self.source = MockStream()
        self.destination.put = AsyncMock()

        await reconnecting_stream_to_pipe_connector(
            source=self.source,
            handler=self.asyncgen_handler,
            destination=self.destination,
            connect=self.connect,
            disconnect=self.disconnect,
            max_reconnect_attempts=2,
            reconnect_exception_type=(ValueError,),
            reconnect_interval=1,
            logger=self.logger)

        # Verify reconnection attempts
        self.assertEqual(self.connect.await_count, 2)
        self.assertEqual(self.disconnect.await_count, 2)

        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1),
            # When reconnected, the test starts the iter_message() anew, thus 1 is sent again
            call(2, timeout=0.1),
            call(4, timeout=0.1)])

    async def test_handling_reconnection_with_reconnect_exception_type_and_unexpected_error(self):
        class MockStream:
            def __init__(self):
                self.reconnected = False

            async def iter_messages(self):
                yield 1
                if not self.reconnected:
                    self.reconnected = True
                    raise ValueError("Disconnected")
                yield 2

        self.source = MockStream()
        self.destination.put = AsyncMock()

        with self.assertRaises(ValueError):
            await reconnecting_stream_to_pipe_connector(
                source=self.source,
                handler=self.asyncgen_handler,
                destination=self.destination,
                connect=self.connect,
                disconnect=self.disconnect,
                max_reconnect_attempts=2,
                reconnect_exception_type=(ConnectionError,),
                reconnect_interval=1,
                logger=self.logger)

        # Verify reconnection attempts
        self.assertEqual(self.connect.await_count, 1)
        self.assertEqual(self.disconnect.await_count, 1)

        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1)])

    async def test_handling_cancelled_stream_error(self):
        # Cancelling the stream results in a clean termination of
        # the stream_to_pipe_connector: The items recieved are put(), the
        # destination is stopped, and the task is cancelled.
        # endless loop for the reconnecting_stream_to_pipe_connector is exited
        class MockStream:
            def __init__(self):
                self.reconnected = False

            async def iter_messages(self):
                yield 1
                raise asyncio.CancelledError

        self.source = MockStream()
        self.destination.put = AsyncMock()

        await reconnecting_stream_to_pipe_connector(
            source=self.source,
            handler=self.asyncgen_handler,
            destination=self.destination,
            connect=self.connect,
            disconnect=self.disconnect,
            max_reconnect_attempts=2,
            reconnect_exception_type=(ConnectionError,),
            reconnect_interval=1,
            logger=self.logger)

        # Verify reconnection attempts
        self.assertEqual(self.connect.await_count, 1)
        self.assertEqual(self.disconnect.await_count, 1)

        self.destination.put.assert_has_awaits([
            call(2, timeout=0.1)])
