import asyncio
import logging
from typing import AsyncGenerator, Awaitable, Callable, Type

from ..pipe.data_types import FromDataT
from ..pipe.protocols import PipeGetPtl
from ..pipe.sentinel import SENTINEL
from .errors import ConditionalGetError, SourceGetError
from .exception_log_manager import log_exception
from .utilities import _no_async_op


async def pipe_to_async_generator(
        pipe: PipeGetPtl[FromDataT],
        *,
        on_condition: Callable[[FromDataT], bool] | None = None,
        on_sentinel_stop: Callable[[], Awaitable[None]] = None,
        call_task_done: bool = True,
        exception: Type[Exception] | None = None,
        logger: logging.Logger | None = None,
) -> AsyncGenerator[FromDataT, None]:
    """
    An async generator that iterates over a Pipe content.

    :param pipe: The pipe to iterate over.
    :param on_condition: An optional function that validates whether the result should be yielded.
    :param on_sentinel_stop: An optional function to call when the pipe is stopped.
    :param call_task_done: Whether to call pipe.task_done() when the pipe is stopped.
    :param exception: An optional exception to raise when the pipe is stopped.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    :return: An async generator that iterates over the queue.
    """
    on_sentinel_stop = on_sentinel_stop or _no_async_op
    while True:
        try:
            item: FromDataT = await pipe.get()

        except (
                asyncio.CancelledError,
                asyncio.TimeoutError) as e:
            log_exception(e, logger, 'WARNING', f"get() raised {e} while waiting for an item. Closing async generator")
            return

        except Exception as e:
            message: str = "Failed while executing {{calling_function}}."
            log_exception(e, logger, 'ERROR', message)
            to_raise: Exception = SourceGetError()
            if exception:
                raise exception(to_raise) from e
            raise to_raise from e

        if item is SENTINEL:
            try:
                await on_sentinel_stop()
            except Exception as e:
                log_exception(e, logger, 'WARNING', "get() was cancelled while waiting for an item.")
                raise e
            if call_task_done:
                pipe.task_done()
            return

        try:
            if on_condition is None or on_condition(item):
                yield item

        except Exception as e:
            to_raise: Exception = ConditionalGetError(
                "Unexpected error with get().",
                item=item)
            if exception:
                raise exception(to_raise) from e
            raise to_raise from e
