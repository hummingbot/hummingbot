import unittest
from unittest.mock import AsyncMock, MagicMock, call

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.errors import (
    ConditionalPutError,
    DestinationPutError,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.utilities import put_on_condition


class TestPutOnCondition(unittest.IsolatedAsyncioTestCase):

    async def async_generator_mock(self, items):
        for item in items:
            yield item

    async def test_normal_operation(self):
        data_generator = self.async_generator_mock([1, 2, 3])
        destination = AsyncMock()
        on_condition = MagicMock(return_value=True)

        await put_on_condition(data_generator, destination=destination, on_condition=on_condition)

        destination.put.assert_has_awaits([call(1), call(2), call(3)])

    async def test_condition_check(self):
        data_generator = self.async_generator_mock([1, 2, 3])
        destination = AsyncMock()
        on_condition = MagicMock(side_effect=lambda x: x % 2 == 0)

        await put_on_condition(data_generator, destination=destination, on_condition=on_condition)

        destination.put.assert_has_awaits([call(2)])

    async def test_exception_in_on_condition(self):
        data_generator = self.async_generator_mock([1])
        destination = AsyncMock()
        on_condition = MagicMock(side_effect=Exception("Condition failed"))

        with self.assertRaises(ConditionalPutError):
            await put_on_condition(data_generator, destination=destination, on_condition=on_condition)

        on_condition.assert_called_once_with(1)
        destination.put.assert_not_awaited()

    async def test_exception_in_destination_put(self):
        data_generator = self.async_generator_mock([1])
        destination = AsyncMock()
        destination.put.side_effect = Exception("Error in put")
        on_condition = MagicMock(return_value=True)

        with self.assertRaises(DestinationPutError):
            await put_on_condition(data_generator, destination=destination, on_condition=on_condition)

    async def test_logging_on_exception(self):
        data_generator = self.async_generator_mock([1])
        destination = AsyncMock()
        destination.put.side_effect = Exception("Error in put")
        on_condition = MagicMock(return_value=True)
        logger = MagicMock()

        with self.assertRaises(DestinationPutError):
            await put_on_condition(data_generator, destination=destination, on_condition=on_condition, logger=logger)

        logger.error.assert_called()

    async def test_async_generator_exhaustion(self):
        data_generator = self.async_generator_mock([1, 2, 3])
        destination = AsyncMock()
        on_condition = MagicMock(return_value=True)

        await put_on_condition(data_generator, destination=destination, on_condition=on_condition)

        # Assert that generator was fully iterated
        self.assertTrue(destination.put.call_count, 3)

    async def test_no_condition_provided(self):
        data_generator = self.async_generator_mock([1, 2, 3])
        destination = AsyncMock()

        await put_on_condition(data_generator, destination=destination)

        # Assert that all items are put since no condition is provided
        destination.put.assert_has_awaits([call(1), call(2), call(3)])


class CustomAsyncMock(AsyncMock):
    async def __call__(self, *args, **kwargs):
        if self._side_effect is not None:
            if isinstance(self._side_effect, BaseException):
                raise self._side_effect from self._side_effect.__cause__
            return await self._side_effect(*args, **kwargs)
        return self._mock_call(*args, **kwargs)
