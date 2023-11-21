import asyncio
import functools
import inspect
import logging
from collections import defaultdict
from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict, Set, Tuple, Type, TypeVar

from .call_or_await import CallOrAwait
from .errors import ExceptionWithItem

T = TypeVar("T")


class ExceptionLogManager:
    _logged_exceptions: Dict[logging.Logger, Set[int]] = defaultdict(set)

    @classmethod
    def _decipher_exception(
            cls,
            exception: BaseException,
            logger: logging.Logger,
    ) -> Tuple[str, ...]:
        """
        Deciphers an exception and returns a tuple of messages to log.

        :param exception: The exception to decipher.
        :param logger: The logger to log the exception to.
        :return: A tuple of messages to log.
        """

        exception_id = id(exception)
        if exception is None or exception_id in cls._logged_exceptions[logger]:
            return ()

        if id(exception) not in cls._logged_exceptions[logger]:
            log = (f"{str(exception) or exception.__class__.__name__}",)
        else:
            log = ()

        e = exception.__cause__
        while e is not None and id(e) not in cls._logged_exceptions[logger]:
            log = log + (f"{str(e) or e.__class__.__name__}",)
            e = e.__cause__

        # Update the history for the specific logger
        cls._logged_exceptions[logger].add(exception_id)
        return log

    @classmethod
    def log_exception(
            cls,
            exception: BaseException,
            logger: logging.Logger | None = None,
            level: str = "ERROR",
            message: str | None = None,
            stack_offset: int = 0,
    ) -> None:
        """
        Logs an exception.

        :param exception: The exception to log.
        :param logger: The logger to log the exception to.
        :param level: The level to log the exception at.
        :param message: An optional message to log before the exception.
        :param stack_offset: The stack offset to use when determining the calling function.
        """
        if exception is None or id(exception) in cls._logged_exceptions[logger]:
            return

        if logger is None:
            return

        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {level}")

        calling_function = inspect.stack()[stack_offset + 1].function

        with suppress(Exception):
            message = message.format(calling_function=calling_function) if message is not None else None

        if message is not None:
            # Register the exception, but do not decipher as the message should have more info
            cls._logged_exceptions[logger].add(id(exception))
            exception = exception.__cause__

        error_log = cls._decipher_exception(exception, logger)

        log_if_possible(logger, level, *reversed(error_log), message)

        if level != "DEBUG":
            log_if_possible(logger, "DEBUG", *reversed(error_log), message)


def log_if_possible(logger, level, *args) -> None:
    """
    Logs a message if possible.

    :param logger: The logger to log the message to.
    :param level: The level to log the message at.
    :param args: The messages to log.
    """
    if logger and logger.isEnabledFor(getattr(logging, level.upper())):
        log_func = getattr(logger, level.lower())
        [log_func(m) for m in args if m is not None]


def log_exception(
        exception: BaseException,
        logger: logging.Logger | None = None,
        level: str = "ERROR",
        message: str = None
):
    """
    Logs an exception.

    :param exception: The exception to log.
    :param logger: The logger to log the exception to.
    :param level: The level to log the exception at.
    :param message: An optional message to log before the exception.
    """
    ExceptionLogManager.log_exception(exception, logger, level, message, 1)


def exception_raised_in_tree(
        exception: Exception,
        exception_type: Type[Exception] | Tuple[Type[Exception]]) -> BaseException | None:
    """
    Retrieve the first exception in a given type in the exception tree.

    :param exception: The exception leaf to descend from.
    :param exception_type: The type of exception to search for.
    """
    while exception is not None:
        if isinstance(exception, exception_type):
            return exception
        exception = exception.__cause__
    return None


def exception_handler_with_shield(
        reraise_list: Tuple[Type[Exception], ...] = None,
        raise_on_cancel: bool = True,
        logger: logging.Logger = None):
    """
    Decorator to handle exceptions in async functions.

    :param reraise_list: A list of exception types to re-raise.
    :param raise_on_cancel: Whether to raise asyncio.CancelledError exceptions.
    :param logger: Logger to use for logging the exception.
    """

    def decorator(func: Callable[..., Awaitable]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            exception_type = kwargs.get('exception', Exception)
            item: Any = args[0] if args else None

            try:
                return await func(*args, **kwargs)

            except asyncio.CancelledError as e:
                if raise_on_cancel:
                    log_exception(e, logger, 'WARNING', "Cancellation caught. Re-raising")
                    raise e
                log_exception(e, logger, 'WARNING', "Cancellation silenced")
                return

            except reraise_list as e:
                log_exception(e, logger, 'ERROR', f"Exception {type(e)} caught. Re-raising")
                raise e

            except Exception as e:
                log_exception(e, logger, 'ERROR', f"Exception {type(e)} caught. Shielding")
                raise_with_item(e, exception_type, item)

        return wrapper

    return decorator


def raise_with_item(e: Exception, to_e: Type[Exception | ExceptionWithItem], item: Any = None) -> None:
    """
    Raises an exception with the provided item.

    :param e: The exception to wrap into an ExceptionWithItem.
    :param to_e: The exception type to raise.
    :param item: The item to raise the exception with.
    :raises Exception: The exception type to raise.
    """
    if to_e is not None:
        if issubclass(to_e, ExceptionWithItem):
            raise to_e(item=item) from e
        raise to_e from e
    raise e


async def try_except_log_only(
        func: CallOrAwait[T],
        *,
        logger: logging.Logger | None = None,
) -> T:
    """
    Try/Except wrapper for calling a function or awaiting a coroutine function.

    :param func: The function or coroutine to call.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    :return: The result of the function call.
    """
    if func is None:
        return None

    try:
        return await func.call(logger=logger)

    except ExceptionWithItem as e:
        name: str = getattr(func.func, '__name__', '[function name undefined]')
        message: str = f"Failed while executing {{calling_function}} for function: {name}."
        log_exception(e, logger, "WARNING", message)


async def try_except_conditional_raise(
        func: CallOrAwait[T],
        *,
        raise_condition: bool = True,
        exception: Type[Exception] | None = None,
        logger: logging.Logger | None = None,
) -> T:
    """
    Try/Except wrapper for calling a function or awaiting a coroutine function.

    :param func: A CallOrAwait function or coroutine to call.
    :param raise_condition: Whether to raise the exception.
    :param exception: Optional custom exception to raise on error.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    :return: The result of the function call.
    :raises Exception: Raises the provided custom exception or propagates the caught exception.
    """
    if func is None:
        return None

    try:
        return await func.call(logger=logger)

    except ExceptionWithItem as e:
        name: str = getattr(func.func, '__name__', '[function name undefined]')
        message: str = f"Failed while executing {{calling_function}} for function: {name}."
        if raise_condition:
            log_exception(e, logger, 'ERROR', message)
            if exception:
                raise exception from e
            raise e
        log_exception(e, logger, 'WARNING', message)
