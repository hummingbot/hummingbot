import functools
import logging
from typing import AsyncGenerator, Callable

from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.protocols import PipeGetPtl, PipePutPtl, PutOperationPtl
from .f_from_get_to_put_logic import from_get_to_put_logic
from .f_pipe_to_async_generator import pipe_to_async_generator
from .utilities import put_on_condition


async def pipe_to_pipe_connector(
        *,
        source: PipeGetPtl[FromDataT],
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
        from_condition: Callable[[FromDataT], bool] | None = None,
        to_condition: Callable[[ToDataT], bool] | None = None,
        put_timeout: float = 0.1,
        logger: logging.Logger | None = None) -> None:
    """
    Connects a source pipe to a destination pipe using a handler function.

    The handler function can be a synchronous function, an asynchronous function,
    a generator function, or an asynchronous generator function.

    If the handler is a generator or async generator, it is expected to yield
    items that will be put into the destination pipe.

    If the handler is a function or async function, it is expected to return
    a single item that will be put into the destination pipe.

    If the task is cancelled, it will attempt to process remaining items in the
    source pipe and put them into the destination pipe, before stopping the
    destination pipe.

    :param source: The source pipe to get items from.
    :param handler: The handler function to process items.
    :param destination: The destination pipe to put items into.
    :param put_timeout: The timeout to use when putting items into the destination pipe.
    :param from_condition: An optional function to filter items from the source pipe.
    :param to_condition: An optional function to filter items to the destination pipe.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    :raises: PipeFullWithItemError and any exceptions raised by pipe.get() other than asyncio.CancelledError.
    """

    get_operation: AsyncGenerator[FromDataT, None] = pipe_to_async_generator(
        source,
        on_condition=from_condition,
        on_sentinel_stop=destination.stop,
        logger=logger,
    )

    put_operation: PutOperationPtl[ToDataT] = functools.partial(
        put_on_condition,
        on_condition=to_condition,
        destination=destination,
        timeout=put_timeout,
        logger=logger,
    )

    await from_get_to_put_logic(
        get_operation=get_operation,
        on_successful_get=source.task_done,
        transform_operation=handler,
        put_operation=put_operation,
        logger=logger)
