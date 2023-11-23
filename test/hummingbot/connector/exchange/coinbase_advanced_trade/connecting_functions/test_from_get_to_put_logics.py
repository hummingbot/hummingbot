import asyncio
import gc
import unittest
from typing import AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock, call, patch

import objgraph

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions import pipe_to_async_generator
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.call_or_await import CallOrAwait
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.errors import DataTransformerError
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic import (
    _HelpersException,
    from_get_to_put_logic,
)
from hummingbot.connector.exchange.coinbase_advanced_trade.pipe import SENTINEL


class GetException(Exception):
    pass


async def async_generator_mock(items, raise_exception: Exception | None = None):
    for item in items:
        yield item
    if raise_exception is not None:
        raise raise_exception


class TestFromGetToPutLogic(unittest.IsolatedAsyncioTestCase):
    all_helpers = (
        "on_successful_put",
        "on_successful_get",
        "on_failed_put",
        "on_failed_get",
        "on_failed_transform",
    )

    async def asyncSetUp(self):
        # mock_async_generator = AsyncGeneratorMock([1, 2, 3])
        # self.get_operation = create_autospec(AsyncGenerator, instance=True, return_value=mock_async_generator)
        self.get_operation = async_generator_mock([1, 2, 3])
        self.get_operation_exception = GetException("Get operation failed")
        self.transform_operation = AsyncMock(side_effect=lambda x: x * 2)
        self.put_operation = AsyncMock()

        for helper in self.all_helpers:
            setattr(self, helper, AsyncMock(name=helper))

        self.log_exception = MagicMock()
        self.logger = MagicMock()

    def assert_helpers_not_called(self, without: List[str] = None):
        if without is None:
            without = []
        for helper in self.all_helpers:
            if helper not in without:
                getattr(self, helper).assert_not_awaited()
                getattr(self, helper).assert_not_called()

    def assert_helpers_called(self, without: List[str] = None):
        if without is None:
            without = []
        for helper in self.all_helpers:
            if helper not in without:
                getattr(self, helper).assert_awaited_with()
                getattr(self, helper).assert_called_with()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_successful_get_and_put(self, try_except_conditional_raise, log_exception_mock):
        # Test
        objgraph.show_growth(limit=3)
        await from_get_to_put_logic(
            get_operation=self.get_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=False,
            raise_for_helpers=False,
            logger=self.logger
        )
        objgraph.show_growth()
        # Assertions
        # Get operation exhausted raises StopAsyncIteration
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        self.put_operation.assert_has_awaits([call(1), call(2), call(3)])
        self.put_operation.assert_has_calls([call(1), call(2), call(3)], any_order=False)
        self.assertEqual(6, len(try_except_conditional_raise.mock_calls))
        # try_except_conditional_raise.assert_has_calls([
        #     call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        # ], any_order=False)

        # These methods are wrapped with try_except_conditional_raise, so they should not be called
        self.assert_helpers_not_called()

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_successful_get_and_put_memory(self, try_except_conditional_raise, log_exception_mock):
        # Test
        await from_get_to_put_logic(
            get_operation=self.get_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=False,
            raise_for_helpers=False,
            logger=self.logger
        )
        objgraph.show_growth(limit=1)
        await from_get_to_put_logic(
            get_operation=self.get_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=False,
            raise_for_helpers=False,
            logger=self.logger
        )
        gc.collect()
        print(gc.get_stats())
        print("- Diff -")
        objgraph.show_growth()
        # objgraph.show_chain(
        #     objgraph.find_backref_chain(
        #         random.choice(objgraph.by_type('CallOrAwait')),
        #         objgraph.is_proper_module),
        #     filename='chain.png')
        # Assertions
        # Get operation exhausted raises StopAsyncIteration
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        self.put_operation.assert_has_awaits([call(1), call(2), call(3)])
        self.put_operation.assert_has_calls([call(1), call(2), call(3)], any_order=False)
        self.assertEqual(6, len(try_except_conditional_raise.mock_calls))
        # try_except_conditional_raise.assert_has_calls([
        #     call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        # ], any_order=False)

        # These methods are wrapped with try_except_conditional_raise, so they should not be called
        self.assert_helpers_not_called()

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_allow_put_none(self, try_except_conditional_raise, log_exception_mock):
        # Test
        async def yield_none():
            for _ in range(3):
                yield

        self.get_operation = yield_none()

        await from_get_to_put_logic(
            get_operation=self.get_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=False,
            raise_for_helpers=False,
            logger=self.logger
        )

        # Assertions
        # Get operation exhausted raises StopAsyncIteration
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        self.put_operation.assert_has_awaits([call(None), call(None), call(None)])
        self.put_operation.assert_has_calls([call(None), call(None), call(None)], any_order=False)
        # Calls get, put success using weak references
        self.assertEqual(6, len(try_except_conditional_raise.mock_calls))

        # These methods are wrapped with try_except_conditional_raise, so they should not be called
        self.assert_helpers_not_called()

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_skip_put_none(self, try_except_conditional_raise, log_exception_mock):
        # Test
        async def yield_none():
            for _ in range(3):
                yield

        self.get_operation = yield_none()

        await from_get_to_put_logic(
            get_operation=self.get_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=True,
            raise_for_helpers=False,
            logger=self.logger
        )

        # Assertions
        # Get operation exhausted raises StopAsyncIteration
        with self.assertRaises(StopAsyncIteration):
            print(await self.get_operation.__anext__())

        self.put_operation.assert_not_awaited()
        self.put_operation.assert_not_called()
        self.assertEqual(3, len(try_except_conditional_raise.mock_calls))
        # try_except_conditional_raise.assert_has_calls([
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        #     call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
        #          raise_condition=False),
        # ], any_order=False)

        # These methods are wrapped with try_except_conditional_raise, so they should not be called
        self.assert_helpers_not_called()

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_failed_get_operation(self, try_except_conditional_raise, log_exception_mock):
        # Simulate a failure in get_operation
        async def failing_get_operation():
            for _ in range(3):
                yield  # Yielding nothing to simulate failure
                raise self.get_operation_exception

        self.get_operation = failing_get_operation()

        # Test
        with self.assertRaises(Exception):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=False,
                logger=self.logger
            )

        # Assertions
        # Get operation raised Exception
        with self.assertRaises(StopAsyncIteration):
            print(await self.get_operation.__anext__())

        try_except_conditional_raise.assert_has_calls([
            call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
                 raise_condition=False)
        ])
        log_exception_mock.assert_has_calls([
            call(self.get_operation_exception, self.logger, 'ERROR')
        ])

        self.assert_helpers_not_called(without=["on_failed_get"])

        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_failed_put_operation(self, try_except_conditional_raise, log_exception_mock):
        # Setup
        original_exception = "Put operation failed"
        self.put_operation.side_effect = Exception(original_exception)

        # Test and Assert
        with self.assertRaises(Exception):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=False,
                logger=self.logger
            )

        # Get operation is not exhausted
        self.assertEqual(2, await self.get_operation.__anext__())

        self.put_operation.assert_has_awaits([call(1)])
        self.put_operation.assert_has_calls([call(1)], any_order=False)
        try_except_conditional_raise.assert_not_called()

        # These methods are wrapped with try_except_conditional_raise, so they should not be called
        self.assert_helpers_not_called(without=["on_failed_put", "on_successful_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_has_calls([
            call(self.put_operation.side_effect, self.logger, 'ERROR'),
        ])
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    #
    # --- Test exceptions in helpers ---
    #
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    async def test_exception_in_on_successful_get(self, log_exception_mock):
        # Setup
        original_helper_exception = "on_successful_get failed"
        self.on_successful_get.side_effect = Exception(original_helper_exception)

        # Test and Assert
        with self.assertRaises(Exception):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=True,
                logger=self.logger
            )

        # Get operation is not exhausted
        self.assertEqual(2, await self.get_operation.__anext__())

        self.put_operation.assert_has_awaits([call(1)])
        self.put_operation.assert_has_calls([call(1)], any_order=False)
        self.on_successful_put.assert_called_once()
        self.on_successful_put.assert_awaited_once()
        self.on_successful_get.assert_called_once()
        self.on_successful_get.assert_awaited_once()

        self.assert_helpers_not_called(without=["on_successful_put", "on_successful_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()

        self.logger.warning.assert_not_called()
        # However, CallOrAwait logs the error
        self.assertIn("try_except_conditional_raise", str(self.logger.error.call_args))

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    async def test_exception_in_on_successful_get_no_raise(self, log_exception_mock):
        # Setup
        original_helper_exception = "on_successful_get failed"
        raise_for_helpers = False
        self.on_successful_get.side_effect = Exception(original_helper_exception)

        # Test and Assert
        await from_get_to_put_logic(
            get_operation=self.get_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=False,
            raise_for_helpers=raise_for_helpers,
            logger=self.logger
        )

        # Get operation is exhausted
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        self.put_operation.assert_has_awaits([
            call(1),
            call(2),
            call(3),
        ], any_order=False)
        self.put_operation.assert_has_calls([
            call(1),
            call(2),
            call(3),
        ], any_order=False)

        self.on_successful_put.assert_has_calls([call()] * 3, any_order=False)
        self.on_successful_put.assert_has_awaits([call()] * 3, any_order=False)
        self.on_successful_get.assert_has_calls([call()] * 3, any_order=False)
        self.on_successful_get.assert_has_awaits([call()] * 3, any_order=False)

        self.assert_helpers_called(without=["on_failed_put", "on_failed_transform", "on_failed_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()

        # Only warn if no raise selected
        self.assertIn("try_except_conditional_raise", str(self.logger.warning.call_args))
        # However, CallOrAwait logs the error
        self.assertIn(original_helper_exception, str(self.logger.error.call_args))

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    async def test_exception_in_on_successful_put(self, log_exception_mock):
        # Setup
        original_helper_exception = "on_successful_put failed"
        self.on_successful_put.side_effect = Exception(original_helper_exception)

        # Test and Assert
        with self.assertRaises(Exception):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=True,
                logger=self.logger
            )

        # Get operation is not exhausted
        self.assertEqual(2, await self.get_operation.__anext__())

        self.put_operation.assert_has_awaits([call(1)])
        self.put_operation.assert_has_calls([call(1)], any_order=False)

        self.on_successful_put.assert_called_once()
        self.on_successful_put.assert_awaited_once()
        self.on_successful_get.assert_called_once()
        self.on_successful_get.assert_awaited_once()

        self.assert_helpers_not_called(without=["on_successful_put", "on_successful_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()

        self.logger.warning.assert_not_called()
        self.assertIn("try_except_conditional_raise", str(self.logger.error.call_args))

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    async def test_exception_in_on_successful_put_no_raise(self, log_exception_mock):
        # Setup
        original_helper_exception = "on_successful_put failed"
        raise_for_helpers = False
        self.on_successful_put.side_effect = Exception(original_helper_exception)

        # Test and Assert
        await from_get_to_put_logic(
            get_operation=self.get_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=False,
            raise_for_helpers=raise_for_helpers,
            logger=self.logger
        )

        # Get operation is exhausted
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        self.put_operation.assert_has_awaits([
            call(1),
            call(2),
            call(3),
        ], any_order=False)
        self.put_operation.assert_has_calls([
            call(1),
            call(2),
            call(3),
        ], any_order=False)

        self.on_successful_put.assert_has_calls([call()] * 3, any_order=False)
        self.on_successful_put.assert_has_awaits([call()] * 3, any_order=False)
        self.on_successful_get.assert_has_calls([call()] * 3, any_order=False)
        self.on_successful_get.assert_has_awaits([call()] * 3, any_order=False)

        self.assert_helpers_called(without=["on_failed_put", "on_failed_transform", "on_failed_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()

        # Only warn if no raise selected
        self.assertIn("try_except_conditional_raise", str(self.logger.warning.call_args))
        # However, CallOrAwait logs the error
        self.assertIn(original_helper_exception, str(self.logger.error.call_args))

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    async def test_exception_in_on_failed_put(self, log_exception_mock):
        original_helper_exception = "on_failed_put failed"
        original_put_exception = "Put operation failed"
        self.on_failed_put.side_effect = Exception(original_helper_exception)
        self.put_operation.side_effect = Exception(original_put_exception)

        with self.assertRaises(Exception):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=False,
                logger=self.logger
            )

        # Put fail stops the loop
        self.assertEqual(2, await self.get_operation.__anext__())

        self.put_operation.assert_has_awaits([call(1)])

        self.on_successful_get.assert_called_once()
        self.on_successful_get.assert_awaited_once()
        self.on_failed_put.assert_awaited_once()

        self.assert_helpers_not_called(without=["on_failed_put", "on_successful_get"])
        log_exception_mock.assert_has_calls([
            call(self.put_operation.side_effect, self.logger, 'ERROR'),
        ])

        # Only warn if no raise selected
        self.assertIn("try_except_log_only", str(self.logger.warning.call_args))
        # However, CallOrAwait logs the error
        self.assertIn(original_helper_exception, str(self.logger.error.call_args))

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    async def test_exception_in_on_failed_get(self, log_exception_mock):
        original_helper_exception = "on_failed_get failed"
        self.on_failed_get.side_effect = Exception(original_helper_exception)
        self.get_operation = async_generator_mock([1], raise_exception=self.get_operation_exception)

        with self.assertRaises(Exception):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=True,
                logger=self.logger
            )

        # Get operation exhausted raises StopAsyncIteration
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        # One successful get/put
        self.put_operation.assert_has_calls([call(1), ], any_order=False)
        self.put_operation.assert_has_awaits([call(1), ], any_order=False)
        self.on_successful_put.assert_called_once()
        self.on_successful_put.assert_awaited_once()
        self.on_successful_get.assert_called_once()
        self.on_successful_get.assert_awaited_once()

        self.on_failed_get.assert_called_once()
        self.on_failed_get.assert_awaited_once()

        self.assert_helpers_called(without=["on_failed_transform", "on_failed_put"])

        log_exception_mock.assert_has_calls([
            call(self.get_operation_exception, self.logger, 'ERROR'),
        ])

        # Since the get raises, we use try_except_log_only, which logs a warning
        self.assertIn("try_except_log_only", str(self.logger.warning.call_args))
        # However, CallOrAwait logs the error
        self.assertIn(original_helper_exception, str(self.logger.error.call_args))

    #
    # --- Test cancellations ---
    #
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_cancelled_get(self, try_except_conditional_raise, log_exception_mock):
        # Setup
        cancelled_error = asyncio.CancelledError()

        async def cancelled_get_operation():
            # Needs to yield to pass the AsyncGenerator assert
            yield 1
            raise cancelled_error

        self.get_operation = cancelled_get_operation()

        # Test and Assert
        with self.assertRaises(asyncio.CancelledError):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=False,
                logger=self.logger
            )

        # Get operation is not exhausted - Well, it raised an exception
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        self.put_operation.assert_has_awaits([call(1)])
        self.put_operation.assert_has_calls([call(1)], any_order=False)

        # We first yield 1, so on_successful_get should be called once
        try_except_conditional_raise.assert_has_calls([
            call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
            call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
        ], any_order=False)

        self.assert_helpers_not_called(without=["on_failed_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_has_calls([
            call(cancelled_error, self.logger),
        ])
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_cancelled_put(self, try_except_conditional_raise, log_exception_mock):
        # Setup
        self.put_operation.side_effect = asyncio.CancelledError()

        # Test and Assert
        with self.assertRaises(asyncio.CancelledError):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=False,
                logger=self.logger
            )

        # Get operation is not exhausted - Well, it raised an exception
        self.assertEqual(2, await self.get_operation.__anext__())

        self.put_operation.assert_has_awaits([call(1)])
        self.put_operation.assert_has_calls([call(1)], any_order=False)

        # We first yield 1, so on_successful_get should be called once
        try_except_conditional_raise.assert_not_called()

        self.assert_helpers_not_called(without=["on_failed_put", "on_successful_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_has_calls([
            call(self.put_operation.side_effect, self.logger),
        ])
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_successful_transformation(self, try_except_conditional_raise, log_exception_mock):
        await from_get_to_put_logic(
            get_operation=self.get_operation,
            transform_operation=self.transform_operation,
            put_operation=self.put_operation,
            on_successful_get=self.on_successful_get,
            on_successful_put=self.on_successful_put,
            on_failed_put=self.on_failed_put,
            on_failed_get=self.on_failed_get,
            skip_put_none=False,
            raise_for_helpers=False,
            logger=self.logger
        )
        # Assertions
        # Get operation exhausted raises StopAsyncIteration
        with self.assertRaises(StopAsyncIteration):
            await self.get_operation.__anext__()

        self.put_operation.assert_has_awaits([call(2), call(4), call(6)])
        self.put_operation.assert_has_calls([call(2), call(4), call(6)], any_order=False)
        try_except_conditional_raise.assert_has_calls([
            call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
            call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
            call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
            call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
            call(CallOrAwait(self.on_successful_put), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
            call(CallOrAwait(self.on_successful_get), exception=_HelpersException, logger=self.logger,
                 raise_condition=False),
        ], any_order=False)

        # These methods are wrapped with try_except_conditional_raise, so they should not be called
        self.assert_helpers_not_called()

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()
        self.logger.warning.assert_not_called()
        self.logger.error.assert_not_called()

    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".log_exception")
    @patch("hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.f_from_get_to_put_logic"
           ".try_except_conditional_raise")
    async def test_transformation_with_exception(self, try_except_conditional_raise, log_exception_mock):
        class TransformError(Exception):
            pass

        original_helper_exception = "Transform error"
        self.transform_operation.side_effect = TransformError(original_helper_exception)

        with self.assertRaises(DataTransformerError):
            await from_get_to_put_logic(
                get_operation=self.get_operation,
                transform_operation=self.transform_operation,
                put_operation=self.put_operation,
                on_successful_get=self.on_successful_get,
                on_successful_put=self.on_successful_put,
                on_failed_put=self.on_failed_put,
                on_failed_get=self.on_failed_get,
                skip_put_none=False,
                raise_for_helpers=False,
                logger=self.logger
            )

        # Get operation is not exhausted
        self.assertEqual(2, await self.get_operation.__anext__())

        self.put_operation.assert_not_awaited()
        self.put_operation.assert_not_called()
        try_except_conditional_raise.assert_not_called()

        # These methods are wrapped with try_except_conditional_raise, so they should not be called
        self.assert_helpers_not_called(without=["on_failed_transform", "on_successful_get"])

        # Nothing is logged if everything runs well
        log_exception_mock.assert_not_called()

        self.logger.warning.assert_not_called()
        # self.assertIn(str(self.transform_operation), str(self.logger.error.call_args))

    async def test_skip_none_post_transformation(self):
        get_operation = async_generator_mock([1, None, 2])
        transform_operation = AsyncMock(side_effect=lambda x: x if x is not None else None)
        put_operation = AsyncMock()

        await from_get_to_put_logic(
            get_operation=get_operation,
            transform_operation=transform_operation,
            put_operation=put_operation,
            skip_put_none=True)

        put_operation.assert_has_awaits([call(1), call(2)])

    async def test_integration(self):
        pipe = MagicMock()
        pipe.get = AsyncMock(side_effect=[1, 2, 3, SENTINEL])
        transform_operation = AsyncMock(side_effect=lambda x: x if x is not None else None)
        put_operation = AsyncMock()

        await from_get_to_put_logic(
            get_operation=pipe_to_async_generator(pipe),
            transform_operation=transform_operation,
            put_operation=put_operation,
            skip_put_none=True)

        put_operation.assert_has_awaits([call(1), call(2), call(3)])

    async def test_integration_get_cancelled(self):
        async def async_generator_transform(x: int) -> AsyncGenerator[int, None]:
            await asyncio.sleep(0)
            yield x * 2
        pipe = AsyncMock()
        pipe.get.side_effect = [1, asyncio.CancelledError, 2, 3, SENTINEL]
        put_operation = AsyncMock()

        await from_get_to_put_logic(
            get_operation=pipe_to_async_generator(pipe),
            transform_operation=async_generator_transform,
            put_operation=put_operation,
            skip_put_none=True)

        put_operation.assert_has_awaits([call(2)])


if __name__ == '__main__':
    unittest.main()
