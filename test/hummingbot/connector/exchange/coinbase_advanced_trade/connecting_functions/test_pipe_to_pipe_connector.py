import asyncio
import unittest
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import pipe_to_pipe_connector
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.errors import (
    DataTransformerError,
    DestinationPutError,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import Pipe
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe.errors import PipeFullWithItemError


class TestPipeToPipeConnector(IsolatedAsyncioWrapperTestCase):
    async def asyncSetUp(self):
        self.handler = AsyncMock()
        self.logger = MagicMock()

        self.source = MagicMock(spec=Pipe)
        self.destination = MagicMock(spec=Pipe)

        # Simulate source pipe items
        self.source_items = [1, 2, 3]
        self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]

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

    async def test_successful_data_transfer(self):
        # Arrange
        self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]

        # Act
        await pipe_to_pipe_connector(
            source=self.source,
            handler=self.sync_handler,
            destination=self.destination,
            logger=self.logger
        )

        # Assert
        self.assertEqual(self.handler.call_count, len(self.source_items))
        self.assertEqual(self.destination.put.call_count, len(self.source_items))

        for item in self.source_items:
            self.destination.put.assert_any_await(item * 10, timeout=0.1)

    async def test_successful_data_transfer_async_handler(self):
        # Arrange
        self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]

        # Act
        await pipe_to_pipe_connector(
            source=self.source,
            handler=self.async_handler,
            destination=self.destination,
            logger=self.logger
        )

        # Assert
        self.assertEqual(self.handler.call_count, len(self.source_items))
        self.assertEqual(self.destination.put.call_count, len(self.source_items))

        for item in self.source_items:
            self.destination.put.assert_any_await(item * 10, timeout=0.1)

    async def test_successful_data_transfer_generator_handler(self):
        # Arrange
        self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]

        # Act
        await pipe_to_pipe_connector(
            source=self.source,
            handler=self.generator_handler,
            destination=self.destination,
            logger=self.logger
        )

        # Assert
        self.assertEqual(self.handler.call_count, len(self.source_items))
        self.assertEqual(self.destination.put.call_count, len(self.source_items))

        for item in self.source_items:
            self.destination.put.assert_any_await(item * 10, timeout=0.1)

    async def test_successful_data_transfer_async_generator_handler(self):
        # Arrange
        self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]

        # Act
        await pipe_to_pipe_connector(
            source=self.source,
            handler=self.asyncgen_handler,
            destination=self.destination,
            logger=self.logger
        )

        # Assert
        self.assertEqual(self.handler.call_count, len(self.source_items))
        self.assertEqual(self.destination.put.call_count, len(self.source_items))

        for item in self.source_items:
            self.destination.put.assert_any_await(item * 10, timeout=0.1)

    async def test_handler_exception(self):
        # Arrange
        self.handler.side_effect = Exception("Handler failed")

        # Act & Assert
        with self.assertRaises(DataTransformerError):
            await pipe_to_pipe_connector(
                source=self.source,
                handler=self.handler,
                destination=self.destination,
                logger=self.logger
            )
        self.handler.assert_called_once()  # Ensure the handler was called before the exception

    async def test_source_pipe_exception(self):
        # Arrange
        self.source.get.side_effect = [Exception("Source failed")]

        # Act & Assert
        with self.assertRaises(Exception) as context:
            await pipe_to_pipe_connector(
                source=self.source,
                handler=self.handler,
                destination=self.destination,
                logger=self.logger
            )
        self.assertEqual("SourceGetError(, item=None)", str(context.exception))

    async def test_destination_pipe_full(self):
        # Arrange
        self.destination.put.side_effect = PipeFullWithItemError()

        # Act & Assert
        with self.assertRaises(DestinationPutError):
            await pipe_to_pipe_connector(
                source=self.source,
                handler=self.async_handler,
                destination=self.destination,
                logger=self.logger
            )


# class TestPipeToPipeConnector(IsolatedAsyncioWrapperTestCase):
#     async def asyncSetUp(self):
#         self.handler = AsyncMock()
#         self.logger = MagicMock()
#
#         self.source = MagicMock(spec=StreamSourcePtl)
#         self.destination = MagicMock(spec=Pipe)
#
#         # Simulate source pipe items
#         self.source_items = [1, 2, 3]
#         self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]
#
#     def sync_handler(self, item: Any) -> Any:
#         self.handler.call_count += 1
#         return item * 10
#
#     async def async_handler(self, item: Any) -> Any:
#         self.handler.call_count += 1
#         self.handler.await_count += 1
#         return item * 10
#
#     def generator_handler(self, item: Any) -> Any:
#         self.handler.call_count += 1
#         yield item * 10
#
#     async def asyncgen_handler(self, item: Any) -> Any:
#         self.handler.call_count += 1
#         self.handler.await_count += 1
#         yield item * 10
#
#     async def test_successful_data_transfer(self):
#         # Arrange
#         self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]
#
#         # Act
#         await pipe_to_pipe_connector(
#             source=self.source,
#             handler=self.sync_handler,
#             destination=self.destination,
#             logger=self.logger
#         )
#
#         # Assert
#         self.assertEqual(self.handler.call_count, len(self.source_items))
#         self.assertEqual(self.destination.put.call_count, len(self.source_items))
#
#         for item in self.source_items:
#             self.destination.put.assert_any_await(item * 10, timeout=0.1)
#
#     async def test_successful_data_transfer_async_handler(self):
#         # Arrange
#         self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]
#
#         # Act
#         await pipe_to_pipe_connector(
#             source=self.source,
#             handler=self.async_handler,
#             destination=self.destination,
#             logger=self.logger
#         )
#
#         # Assert
#         self.assertEqual(self.handler.call_count, len(self.source_items))
#         self.assertEqual(self.destination.put.call_count, len(self.source_items))
#
#         for item in self.source_items:
#             self.destination.put.assert_any_await(item * 10, timeout=0.1)
#
#     async def test_successful_data_transfer_generator_handler(self):
#         # Arrange
#         self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]
#
#         # Act
#         await pipe_to_pipe_connector(
#             source=self.source,
#             handler=self.generator_handler,
#             destination=self.destination,
#             logger=self.logger
#         )
#
#         # Assert
#         self.assertEqual(self.handler.call_count, len(self.source_items))
#         self.assertEqual(self.destination.put.call_count, len(self.source_items))
#
#         for item in self.source_items:
#             self.destination.put.assert_any_await(item * 10, timeout=0.1)
#
#     async def test_successful_data_transfer_async_generator_handler(self):
#         # Arrange
#         self.source.get.side_effect = self.source_items + [asyncio.CancelledError()]
#
#         # Act
#         await pipe_to_pipe_connector(
#             source=self.source,
#             handler=self.asyncgen_handler,
#             destination=self.destination,
#             logger=self.logger
#         )
#
#         # Assert
#         self.assertEqual(self.handler.call_count, len(self.source_items))
#         self.assertEqual(self.destination.put.call_count, len(self.source_items))
#
#         for item in self.source_items:
#             self.destination.put.assert_any_await(item * 10, timeout=0.1)
#
#     async def test_handler_exception(self):
#         # Arrange
#         self.handler.side_effect = Exception("Handler failed")
#
#         # Act & Assert
#         with self.assertRaises(DataTransformerError) as context:
#             await pipe_to_pipe_connector(
#                 source=self.source,
#                 handler=self.handler,
#                 destination=self.destination,
#                 logger=self.logger
#             )
#         self.handler.assert_called_once()  # Ensure the handler was called before the exception
#
#     async def test_source_pipe_exception(self):
#         # Arrange
#         self.source.get.side_effect = [Exception("Source failed")]
#
#         # Act & Assert
#         with self.assertRaises(Exception) as context:
#             await pipe_to_pipe_connector(
#                 source=self.source,
#                 handler=self.handler,
#                 destination=self.destination,
#                 logger=self.logger
#             )
#         self.assertEqual("SourceGetError(, item=None)", str(context.exception))
#
#     async def test_destination_pipe_full(self):
#         # Arrange
#         self.destination.put.side_effect = PipeFullWithItemError()
#
#         # Act & Assert
#         with self.assertRaises(DestinationPutError):
#             await pipe_to_pipe_connector(
#                 source=self.source,
#                 handler=self.async_handler,
#                 destination=self.destination,
#                 logger=self.logger
#             )
#
#     async def test_cancellation_handling(self):
#         # Arrange
#         # Act & Assert
#         # with self.assertRaises(asyncio.CancelledError):
#         await pipe_to_pipe_connector(
#             source=self.source,
#             handler=self.sync_handler,
#             destination=self.destination,
#             logger=self.logger
#         )
#
#         print(self.logger.warning.mock_calls)
#         print(self.logger.error.mock_calls)
#         # Ensure the destination put was attempted for remaining items
#         self.assertEqual(self.destination.put.call_count, len(self.source_items))


if __name__ == "__main__":
    unittest.main()
