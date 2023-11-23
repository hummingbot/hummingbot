import asyncio
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest import TestCase
from unittest.mock import MagicMock, call, patch

import objgraph

from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.call_or_await import CallOrAwait
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.errors import ExceptionWithItem
from hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.exception_log_manager import (
    ExceptionLogManager,
    exception_handler_with_shield,
    log_if_possible,
    try_except_conditional_raise,
    try_except_log_only,
)


class TestExceptionLogManager(TestCase):

    def test_log_if_possible(self):
        logger = MagicMock()
        logger.isEnabledFor.return_value = True
        log_if_possible(logger, 'INFO', 'Test message')

        logger.info.assert_called_once_with('Test message')

    def test_log_if_possible_memory(self):
        logger = MagicMock()
        logger.isEnabledFor.return_value = True
        objgraph.show_growth(limit=1)
        log_if_possible(logger, 'INFO', 'Test message')
        del logger
        print("- Diff -")
        objgraph.show_growth()

    def test_log_if_possible_no_logger(self):
        logger = None
        # No exception should be raised when logger is None
        log_if_possible(logger, 'INFO', 'Test message')

    def test_log_if_possible_disabled_level(self):
        logger = MagicMock()
        logger.isEnabledFor.return_value = False
        log_if_possible(logger, 'DEBUG', 'Test message')

        logger.debug.assert_not_called()

    def test__decipher_exception_simple(self):
        exception = Exception("Test exception")
        log = ExceptionLogManager._decipher_exception(exception, logger=MagicMock())

        self.assertEqual(log, ('Test exception',))

    def test__decipher_exception_with_cause(self):
        def func():
            raise Exception("Cause exception")

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    raise Exception("Intermediate exception") from e
            except Exception as e:
                raise Exception("Test exception") from e
        except Exception as exception:
            log = ExceptionLogManager._decipher_exception(exception, logger=logger)
            self.assertEqual(('Test exception', 'Intermediate exception', 'Cause exception'), log)

    def test__decipher_exception_no_error_message_logs_exception_name(self):
        def func():
            raise ValueError

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    raise TypeError from e
            except Exception as e:
                raise RuntimeError from e
        except Exception as exception:
            log = ExceptionLogManager._decipher_exception(exception, logger=logger)
            self.assertEqual(('RuntimeError', 'TypeError', 'ValueError'), log)

    def test_log_exception(self):
        logger = MagicMock()
        exception = Exception("Test exception")
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.exception_log_manager'
                   '.inspect') as mock_stack:
            mock_stack.stack.return_value = [MagicMock(), MagicMock(function='test_func')]
            ExceptionLogManager.log_exception(exception, logger)

        logger.error.assert_has_calls([
            call('Test exception'),
            # call('None'),  # No message in log_exception
        ])

    def test_log_exception_with_message(self):
        logger = MagicMock()
        exception = Exception("Test exception")
        with patch('hummingbot.connector.exchange.coinbase_advanced_trade.connecting_functions.exception_log_manager'
                   '.inspect') as mock_stack:
            mock_stack.stack.return_value = [MagicMock(), MagicMock(function='test_func')]
            ExceptionLogManager.log_exception(exception, logger, message="Custom message in {calling_function}")

        logger.error.assert_has_calls([
            call('Custom message in test_func'),
        ])

    def test_log_exception_no_logger(self):
        exception = Exception("Test exception")
        # No exception should be raised when logger is None
        ExceptionLogManager.log_exception(exception)

    def test_log_exception_with_cause(self):
        def func():
            raise Exception("Cause exception")

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    raise Exception("Intermediate exception") from e
            except Exception as e:
                raise Exception("Test exception") from e
        except Exception as exception:
            ExceptionLogManager.log_exception(exception, logger=logger)

        logger.error.assert_has_calls([
            call('Cause exception'),
            call('Intermediate exception'),
            call('Test exception'),
        ])

    def test_log_exception_with_cause_log_twice(self):
        def func():
            raise Exception("Cause exception")

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    raise Exception("Intermediate exception") from e
            except Exception as e:
                raise Exception("Test exception") from e
        except Exception as exception:
            ExceptionLogManager.log_exception(exception, logger=logger, message="Logging test exception")
            ExceptionLogManager.log_exception(exception, logger=logger, message="Mistaken test exception")

        logger.error.assert_has_calls([
            call('Cause exception'),
            call('Intermediate exception'),
            call('Logging test exception'),
        ])

    def test_log_exception_with_cause_and_logging_message(self):
        def func():
            raise Exception("Cause exception")

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    raise Exception("Intermediate exception") from e
            except Exception as e:
                raise Exception("Test exception") from e
        except Exception as exception:
            ExceptionLogManager.log_exception(exception, logger=logger, message="Logging test exception")

        logger.error.assert_has_calls([
            call('Cause exception'),
            call('Intermediate exception'),
            call('Logging test exception'),
        ])

    def test_log_exception_with_cause_staged_log(self):
        def func():
            raise Exception("Cause exception")

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    raise Exception("Intermediate exception") from e
            except Exception as e:
                ExceptionLogManager.log_exception(e, logger=logger)
                raise Exception("Test exception") from e
        except Exception as exception:
            ExceptionLogManager.log_exception(exception, logger=logger)

        logger.error.assert_has_calls([
            call('Cause exception'),
            call('Intermediate exception'),
            call('Test exception'),
        ])

    def test_log_exception_with_cause_staged_log_with_message(self):
        def func():
            raise Exception("Cause exception")

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    raise Exception("Intermediate exception") from e
            except Exception as e:
                ExceptionLogManager.log_exception(e, logger=logger, message="Message for intermediate exception")
                raise Exception("Test exception") from e
        except Exception as exception:
            ExceptionLogManager.log_exception(exception, logger=logger)

        logger.error.assert_has_calls([
            call('Cause exception'),
            call('Message for intermediate exception'),
            call('Test exception'),
        ])

    def test_log_exception_with_cause_all_logged(self):
        def func():
            raise Exception("Cause exception")

        logger = MagicMock()
        try:
            try:
                try:
                    func()
                except Exception as e:
                    ExceptionLogManager.log_exception(e, logger=logger, message="Message for cause exception")
                    raise Exception("Intermediate exception") from e
            except Exception as e:
                ExceptionLogManager.log_exception(e, logger=logger, message="Message for intermediate exception")
                raise Exception("Test exception") from e
        except Exception as exception:
            ExceptionLogManager.log_exception(exception, logger=logger, message="Logging test exception")

        logger.error.assert_has_calls([
            call('Message for cause exception'),
            call('Message for intermediate exception'),
            call('Logging test exception'),
        ])


class CustomException(Exception):
    pass


class AnotherCustomException(Exception):
    pass


class TestExceptionHandlerWithShield(IsolatedAsyncioWrapperTestCase):
    def setUp(self):
        self.logger = MagicMock()

    async def test_no_exception(self):
        @exception_handler_with_shield(reraise_list=(CustomException,), logger=self.logger)
        async def test_func():
            return 42

        result = await (test_func())
        self.assertEqual(result, 42)
        self.logger.error.assert_not_called()

    async def test_cancelled_error(self):
        @exception_handler_with_shield(reraise_list=(CustomException,), logger=self.logger)
        async def test_func():
            raise asyncio.CancelledError()

        with self.assertRaises(asyncio.CancelledError):
            await (test_func())
        self.logger.warning.assert_called_once()

    async def test_cancelled_error_silenced(self):
        @exception_handler_with_shield(
            reraise_list=(CustomException,),
            raise_on_cancel=False,
            logger=self.logger)
        async def test_func():
            raise asyncio.CancelledError()

        await (test_func())
        self.logger.warning.assert_called_once()

    async def test_reraise_exception(self):
        @exception_handler_with_shield(reraise_list=(CustomException,), logger=self.logger)
        async def test_func():
            raise CustomException()

        with self.assertRaises(CustomException):
            await (test_func())
        self.logger.error.assert_called_once()

    async def test_other_exception(self):
        @exception_handler_with_shield(reraise_list=(CustomException,), logger=self.logger)
        async def test_func():
            raise AnotherCustomException()

        with self.assertRaises(Exception) as e:
            await (test_func())
            self.assertEqual(e.__cause__, AnotherCustomException())
        self.logger.error.assert_called_once()

    async def test_reraise_handling(self):
        @exception_handler_with_shield(reraise_list=(ValueError,), logger=self.logger)
        async def test_func():
            raise ValueError()

        with self.assertRaises(ValueError):
            await (test_func())
        self.logger.error.assert_called_once()

    async def test_logging(self):
        @exception_handler_with_shield(reraise_list=(CustomException,), logger=self.logger)
        async def test_func():
            raise CustomException("Test Error")

        with self.assertRaises(CustomException):
            await (test_func())
        self.logger.error.assert_called_once_with(f"Exception <class '{__name__}.CustomException'> caught. Re-raising")


class TestTryExceptLogOnly(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        self.logger = MagicMock()

    def regular_function_no_error(self):
        return 42

    def regular_function_with_error(self):
        raise ValueError("Regular function error")

    async def async_function_no_error(self):
        await asyncio.sleep(0)
        return 42

    async def async_function_with_error(self):
        await asyncio.sleep(0)
        raise ValueError("Async function error")

    async def test_regular_function_no_error(self):
        result = await try_except_log_only(CallOrAwait(self.regular_function_no_error), logger=self.logger)

        self.assertEqual(42, result)
        self.logger.warning.assert_not_called()

    async def test_regular_function_no_error_memory(self):
        call_or_await = CallOrAwait(self.regular_function_no_error)
        # Generate similar objects to try to decipher the memory leak
        [await try_except_log_only(call_or_await.get_weakref(), logger=self.logger) for _ in range(100)]
        objgraph.show_growth(limit=1)
        [await try_except_log_only(call_or_await.get_weakref(), logger=self.logger) for _ in range(100)]
        print("- Diff -")
        objgraph.show_growth()
        self.logger.warning.assert_not_called()

    async def test_regular_function_with_error(self):
        await try_except_log_only(CallOrAwait(self.regular_function_with_error), logger=self.logger)
        self.logger.warning.assert_called()
        # CallOrAwait logs an error
        self.assertIn("Regular function error", self.logger.error.call_args[0][0])
        # try_except_log_only logs a warning
        self.assertIn("try_except_log_only", self.logger.warning.call_args[0][0])
        self.assertIn("regular_function_with_error", self.logger.warning.call_args[0][0])

    async def test_async_function_no_error(self):
        result = await try_except_log_only(CallOrAwait(self.async_function_no_error), logger=self.logger)
        self.assertEqual(42, result)
        self.logger.warning.assert_not_called()

    async def test_async_function_with_error(self):
        await try_except_log_only(CallOrAwait(self.async_function_with_error), logger=self.logger)
        self.logger.warning.assert_called()
        # CallOrAwait logs an error
        self.assertIn("Async function error", self.logger.error.call_args[0][0])
        # try_except_log_only logs a warning
        self.assertIn("try_except_log_only", self.logger.warning.call_args[0][0])
        self.assertIn("async_function_with_error", self.logger.warning.call_args[0][0])

    async def test_function_is_none(self):
        result = await try_except_log_only(None, logger=self.logger)
        self.assertIsNone(result)
        self.logger.warning.assert_not_called()


class TestTryExceptConditionalRaise(IsolatedAsyncioWrapperTestCase):

    def setUp(self):
        self.logger = MagicMock()

    def regular_function_no_error(self):
        return 42

    def regular_function_with_error(self):
        raise ValueError("Regular function error")

    async def async_function_no_error(self):
        await asyncio.sleep(0)
        return 42

    async def async_function_with_error(self):
        await asyncio.sleep(0)
        raise ValueError("Async function error")

    async def test_function_no_error(self):
        result = await try_except_conditional_raise(CallOrAwait(self.regular_function_no_error), logger=self.logger)
        self.assertEqual(result, 42)
        self.logger.error.assert_not_called()

    async def test_regular_function_no_error_memory(self):
        call_or_await = CallOrAwait(self.regular_function_no_error)
        # Generate similar objects to try to decipher the memory leak
        [await try_except_conditional_raise(call_or_await.get_weakref(), logger=self.logger) for _ in range(100)]
        objgraph.show_growth(limit=1)
        [await try_except_conditional_raise(call_or_await.get_weakref(), logger=self.logger) for _ in range(100)]
        print("- Diff -")
        objgraph.show_growth()
        self.logger.warning.assert_not_called()

    async def test_async_function_no_error(self):
        result = await try_except_conditional_raise(CallOrAwait(self.async_function_no_error), logger=self.logger)
        self.assertEqual(result, 42)
        self.logger.error.assert_not_called()

    async def test_function_with_error_raise_condition_true(self):
        with self.assertRaises(ExceptionWithItem):
            await try_except_conditional_raise(CallOrAwait(self.regular_function_with_error), logger=self.logger)

        # CallOrAwait logs an error
        self.assertIn("regular_function_with_error", self.logger.error.call_args_list[0][0][0])
        self.assertIn("Regular function error", self.logger.error.call_args_list[0][0][0])
        # try_except_conditional_raise logs an error
        self.assertIn("try_except_conditional_raise", self.logger.error.call_args_list[1][0][0])
        self.assertIn("regular_function_with_error", self.logger.error.call_args_list[1][0][0])

    async def test_function_with_error_raise_condition_false(self):
        await try_except_conditional_raise(CallOrAwait(self.regular_function_with_error), raise_condition=False,
                                           logger=self.logger)
        self.logger.warning.assert_called_once()

    async def test_function_is_none(self):
        result = await try_except_conditional_raise(None, logger=self.logger)
        self.assertIsNone(result)
        self.logger.error.assert_not_called()

    async def test_function_with_custom_exception(self):
        custom_exception = TypeError("Custom error")
        with self.assertRaises(TypeError):
            await try_except_conditional_raise(CallOrAwait(self.regular_function_with_error),
                                               exception=custom_exception,
                                               logger=self.logger)
        # CallOrAwait logs an error
        self.assertIn("regular_function_with_error", self.logger.error.call_args_list[0][0][0])
        self.assertIn("Regular function error", self.logger.error.call_args_list[0][0][0])
        # try_except_conditional_raise logs an error
        self.assertIn("try_except_conditional_raise", self.logger.error.call_args_list[1][0][0])
        self.assertIn("regular_function_with_error", self.logger.error.call_args_list[1][0][0])
