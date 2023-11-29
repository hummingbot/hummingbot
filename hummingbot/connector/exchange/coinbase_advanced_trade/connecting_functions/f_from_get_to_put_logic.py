import asyncio
import functools
import logging
from typing import AsyncGenerator, Callable, Coroutine, Iterable, List, Tuple

from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.protocols import PutOperationPtl
from .call_or_await import CallOrAwait
from .errors import ExceptionWithItem, SourceGetError, _ShieldingException
from .exception_log_manager import log_exception, try_except_conditional_raise, try_except_log_only
from .utilities import transform_async_generator

_HelpersT = Callable[[], Coroutine[None, None, None] | None] | None


class _TransformException(ExceptionWithItem):
    pass


class _HelpersException(Exception):
    pass


async def from_get_to_put_logic(
        *,
        get_operation: AsyncGenerator[FromDataT, None],
        transform_operation: HandlerT | None = None,
        put_operation: PutOperationPtl[ToDataT],
        on_successful_get: _HelpersT = None,
        on_failed_get: _HelpersT = None,
        on_failed_transform: _HelpersT = None,
        on_successful_put: _HelpersT = None,
        on_failed_put: _HelpersT = None,
        skip_put_none: bool = True,
        raise_for_helpers: bool = True,
        logger: logging.Logger | None = None,
) -> None:
    """
    Transfers data from an AsyncGenerator to a PutOperation-capable destination.

    :param get_operation: An AsyncGenerator that yields items to be put into the destination.
    :param transform_operation: An optional function to transform items before putting them into the destination.
    :param put_operation: A PutOperation that puts items into the destination.
    :param on_successful_get: An optional function to call when an item is successfully retrieved from the source.
    :param on_failed_get: An optional function to call when an item is unsuccessfully retrieved from the source.
    :param on_failed_transform: An optional function to call when an item is unsuccessfully transformed.
    :param on_successful_put: An optional function to call when an item is successfully put into the destination.
    :param on_failed_put: An optional function to call when an item is not successfully put into the destination.
    :param skip_put_none: Whether to skip putting None items into the destination.
    :param raise_for_helpers: Whether to continue the get/put loop if a helper function raises an exception.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    :raises: Any exceptions raised by the get_operation, as well as PipeFullWithItemError.
    """
    if not isinstance(get_operation, AsyncGenerator):
        raise TypeError("get_operation must be an AsyncGenerator.")

    if all((not isinstance(put_operation, Iterable),
            not isinstance(put_operation, PutOperationPtl))):
        raise TypeError("put_operation must be a PutOperationPtl or an Iterable of PutOperationPtl.")

    put_operations: List[PutOperationPtl[FromDataT, ToDataT]] = [put_operation] if isinstance(put_operation, PutOperationPtl) else put_operation

    for put_operation_item in list(put_operations):
        if not asyncio.iscoroutinefunction(put_operation_item):
            put_operations.remove(put_operation_item)

    if put_operations is []:
        raise TypeError("put_operation cannot be None.")

    _on_successful_get: CallOrAwait = CallOrAwait(on_successful_get)
    _on_successful_put: CallOrAwait = CallOrAwait(on_successful_put)
    _on_failed_get: CallOrAwait = CallOrAwait(on_failed_get)
    _on_failed_put: CallOrAwait = CallOrAwait(on_failed_put)
    _on_failed_transform: CallOrAwait = CallOrAwait(on_failed_transform)

    _try_helper = functools.partial(
        try_except_conditional_raise,
        exception=_HelpersException,
        logger=logger,
        raise_condition=raise_for_helpers)

    _try_helper_log_only = functools.partial(
        try_except_log_only,
        logger=logger)

    _transform: Callable[[AsyncGenerator[FromDataT, None]], AsyncGenerator[FromDataT, None]] = functools.partial(
        transform_async_generator,
        transform=transform_operation,
        exception=_TransformException,
        logger=logger)

    _put: Callable[[FromDataT], Coroutine] = functools.partial(
        _inner_try_except_put,
        put_operations=tuple(put_operations),
        on_successful_put=functools.partial(_try_helper, _on_successful_put.get_weakref()),
        on_failed_put=functools.partial(_try_helper_log_only, _on_failed_put.get_weakref()),
        skip_put_none=skip_put_none,
        logger=logger)

    try:
        data_gen: AsyncGenerator[FromDataT, None] = get_operation

        if transform_operation is not None:
            data_gen = _transform(data_gen)

        _on_success = functools.partial(_try_helper, _on_successful_get.get_weakref())
        async for msg in data_gen:
            await _put(msg)
            await _on_success()

    except _HelpersException as e:
        # Put operation succeeded, but on_successful_get failed and raise_for_helpers is True.
        raise e.__cause__ from e.__cause__.__cause__

    except _ShieldingException as e:
        await _try_helper_log_only(_on_successful_get.get_weakref())
        if not isinstance(e.__cause__, _HelpersException):
            # Put operation failed.
            raise e.__cause__ from e.__cause__.__cause__
        # Put operation succeeded, but on_successful_put failed and raise_for_helpers is True.
        raise e.__cause__.__cause__ from e.__cause__.__cause__.__cause__

    except _TransformException as e:
        if isinstance(e.__cause__, SourceGetError):
            raise e.__cause__.__cause__ from e.__cause__.__cause__.__cause__
        await _try_helper_log_only(_on_successful_get.get_weakref())
        await _try_helper_log_only(_on_failed_transform.get_weakref())
        raise e.__cause__ from e.__cause__.__cause__

    except asyncio.CancelledError as e:
        log_exception(e, logger)
        await _try_helper_log_only(_on_failed_get.get_weakref())
        raise asyncio.CancelledError from e

    except Exception as e:
        log_exception(e, logger, 'ERROR')
        await _try_helper_log_only(_on_failed_get.get_weakref())
        raise e


async def _inner_try_except_put(
        msg: FromDataT,
        put_operations: Tuple[PutOperationPtl[ToDataT], ...],
        on_successful_put: Callable[[], Coroutine] = None,
        on_failed_put: Callable[[], Coroutine] = None,
        skip_put_none: bool = True,
        logger: logging.Logger | None = None,
) -> None:
    """
    Puts a message into a destination, and calls a post-put function.

    :param msg: The message to put into the destination.
    :param put_operations: A Tuple of PutOperation that puts items into the destination.
    :param try_helper: A function to wrap helper functions with.
    :param on_failed_put: An optional function to call when an item is unsuccessfully put into the destination.
    :param skip_put_none: Whether to skip putting None items into the destination.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    :raises: Any exceptions raised by the put_operation, as well as _ShieldingException.
    """
    if msg is None and skip_put_none:
        return

    for put_operation in put_operations:
        try:
            await put_operation(msg)
            await on_successful_put()

        except _HelpersException as e:
            raise _ShieldingException from e

        except asyncio.CancelledError as e:
            log_exception(e, logger)
            await on_failed_put()
            raise _ShieldingException from e

        except Exception as e:
            log_exception(e, logger, 'ERROR')
            await on_failed_put()
            raise _ShieldingException from e