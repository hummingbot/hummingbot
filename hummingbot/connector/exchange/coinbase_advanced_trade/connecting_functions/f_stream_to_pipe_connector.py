import functools
import inspect
import logging
from typing import AsyncGenerator, Callable, Tuple

from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.protocols import PipePutPtl, PutOperationPtl
from ..pipeline.protocols import StreamMessageIteratorPtl, StreamSourcePtl
from .errors import _ReconnectError
from .exception_log_manager import exception_raised_in_tree, log_exception
from .f_from_get_to_put_logic import from_get_to_put_logic
from .utilities import _no_sync_op, put_on_condition

_StreamSourcePtl = StreamMessageIteratorPtl[FromDataT] | StreamSourcePtl[FromDataT]


async def stream_to_pipe_connector(
        *,
        source: _StreamSourcePtl,
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
        allow_reconnect: bool | None = False,
        on_successful_reconnect: Callable[[], None] | None = _no_sync_op,
        reconnect_exception_type: Tuple[type[Exception]] = (ConnectionError,),
        put_timeout: float = 0.1,
        logger: logging.Logger | None = None) -> None:
    """
    Connects a source StreamMessageIteratorPtl to a destination pipe using a handler function.

    The handler function can be a synchronous function, an asynchronous function,
    a generator function, or an asynchronous generator function.

    If the handler is a generator or async generator, it is expected to yield
    items that will be put into the destination pipe.

    If the handler is a function or async function, it is expected to return
    a single item that will be put into the destination pipe.

    If the task is cancelled, it will stop the destination pipe.

    :param source: The source stream to receive items from.
    :param handler: The handler function to process items.
    :param destination: The destination pipe to put items into.
    :param allow_reconnect: Whether to raise exceptions that occur while listening to the stream.
    :param on_successful_reconnect: A function to call when the stream is successfully reconnected.
    :param reconnect_exception_type: The exception types to allow reconnecting on.
    :param put_timeout: The timeout to use when putting items into the destination pipe.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    """

    if callable(source) and inspect.isawaitable(awaitable := source()):
        source: StreamMessageIteratorPtl[FromDataT] = await awaitable

    get_operation: AsyncGenerator[FromDataT, None] = source.iter_messages()  # type: ignore # Pycharm

    put_operation: PutOperationPtl[ToDataT] = functools.partial(
        put_on_condition,
        destination=destination,
        timeout=put_timeout)

    try:
        await from_get_to_put_logic(
            get_operation=get_operation,
            transform_operation=handler,
            put_operation=put_operation,
            on_successful_get=on_successful_reconnect,
            # on_failed_get=destination.stop if not allow_reconnect else None,
            # on_failed_transform=destination.stop if not allow_reconnect else None,
            # on_failed_put=destination.stop if not allow_reconnect else None,
            logger=logger)

        if not allow_reconnect:
            await destination.stop()

    except Exception as e:
        reconnect_exception: BaseException = exception_raised_in_tree(e, reconnect_exception_type)
        if not allow_reconnect or reconnect_exception is None:
            await destination.stop()
            raise e

        log_exception(
            reconnect_exception,
            logger,
            'WARNING',
            "Allowing possible reconnect attempt")
        raise _ReconnectError from reconnect_exception
