import asyncio
import inspect
import logging
from typing import Any, AsyncGenerator, Awaitable, Callable, Coroutine, Generator, List

from ..pipe.data_types import FromTupleDataT
from ..pipe.errors import PipeFullError
from ..pipe.protocols import PipeGetPtl, PipePutPtl, PutOperationPtl
from ..pipe.sentinel import SENTINEL, Sentinel, sentinel_ize
from ..pipe.utilities import log_if_possible, pipe_snapshot
from .data_types import FromDataT, HandlerT, ToDataT
from .protocols import StreamMessageIteratorPtl, StreamSourcePtl


async def pipe_to_async_generator(pipe: PipeGetPtl[FromDataT]) -> AsyncGenerator[FromDataT, None]:
    """
    An async generator that iterates over a Pipe content.

    :param pipe: The pipe to iterate over.
    :return: An async generator that iterates over the queue.
    :raises: Any exceptions raised by pipe.get() other than asyncio.CancelledError.
    """
    while True:
        try:
            item = await pipe.get()
            if item is SENTINEL:
                return
            yield item
        except asyncio.CancelledError:
            return
        except Exception as e:
            raise e


async def _process_residual_data_on_cancel(
        source: PipeGetPtl[FromDataT],
        put_operation: PutOperationPtl[FromDataT],
        destination: PipePutPtl[ToDataT],
        logger: logging.Logger | None = None) -> None:
    """
    Helper function to process residual data on cancellation of a task.
    """
    messages: FromTupleDataT = sentinel_ize(await pipe_snapshot(source))
    try:
        [await put_operation(m) for m in messages[:-1]]
    except PipeFullError:
        log_if_possible(logger,
                        'ERROR',
                        "Data loss: Attempted to flush upstream Pipe on cancellation, however, "
                        "downstream Pipe is full.")
    await destination.stop()


async def pipe_to_pipe_connector(
        *,
        source: PipeGetPtl[FromDataT],
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
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
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    """

    put_operation: PutOperationPtl[FromDataT] = _get_pipe_put_operation_for_handler(
        handler=handler,
        destination=destination)

    wait_time: float = 0.1
    max_retries: int = 3
    max_wait_time_per_retry: int = 1

    while True:
        try:
            msg: FromDataT | Sentinel = await source.get()

            # The source pipe was stopped and sent the SENTINEL
            if msg is SENTINEL:
                # Stop the destination pipe in turn
                await destination.stop()
                source.task_done()
                break

            # Raises PipeFullError if the destination pipe is full after wait/retries
            await put_operation(
                msg,
                wait_time=wait_time,
                max_retries=max_retries,
                max_wait_time_per_retry=max_wait_time_per_retry)

            source.task_done()
            await asyncio.sleep(0)

        except PipeFullError:
            log_if_possible(logger,
                            'ERROR',
                            f"Data loss: Downstream Pipe remained full while attempting to transfer the data\n"
                            f"Pipe retry parameters:"
                            f"\twait_time={wait_time}\n"
                            f"\tmax_retries={max_retries}\n"
                            f"\tmax_wait_time_per_retry={max_wait_time_per_retry}\n")

        except asyncio.CancelledError as e:
            log_if_possible(logger, 'WARNING', "Task was cancelled. Attempting to process remaining items.")
            await _process_residual_data_on_cancel(source, put_operation, destination, logger)
            raise asyncio.CancelledError from e

        except Exception as e:
            log_if_possible(logger, 'exception', f"An unexpected error occurred: {e}")
            raise e


async def multipipe_to_pipe_connector(
        *,
        sources: List[PipeGetPtl[FromDataT]],
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
        logger: logging.Logger | None = None) -> None:
    """
    Connects multiple source pipes to a destination pipe using a handler function.

    The handler function can be a synchronous function, an asynchronous function,
    a generator function, or an asynchronous generator function.

    If the handler is a generator or async generator, it is expected to yield
    items that will be put into the destination pipe.

    If the handler is a function or async function, it is expected to return
    a single item that will be put into the destination pipe.

    If the task is cancelled, it will attempt to process remaining items in the
    source pipe and put them into the destination pipe, before stopping the
    destination pipe.

    :param sources: The source pipes to get items from.
    :param handler: The handler function to process items.
    :param destination: The destination pipe to put items into.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    """
    # Create a task for each source
    _tasks: Generator[Coroutine[None, None, Any]] = (
        pipe_to_pipe_connector(source=source, handler=handler, destination=destination, logger=logger)
        for source in sources
    )

    # Run all tasks concurrently
    await asyncio.gather(*_tasks)


# async def pipe_to_split_destinations(
#        *,
#        source: PipeGetPtl[FromDataT],
#        handler: HandlerT | None,
#        destinations: List[Tuple[Callable[[ToDataT], bool], PipePutPtl[ToDataT]]],
#        logger: logging.Logger | None = None) -> None:
#    """
#    Distributes items conditionally from a source pipe to multiple destination pipes
#    using a handler function and a validating function for each destination.
#
#    The handler function can be a synchronous function, an asynchronous function,
#    a generator function, or an asynchronous generator function.
#
#    If the handler is a generator or async generator, it is expected to yield
#    items that will be put into the destination pipes.
#
#    If the handler is a function or async function, it is expected to return
#    a single item that will be put into the destination pipes.
#
#    If the task is cancelled, it will stop the destination pipes.
#
#    :param source: The source pipe to get items from.
#    :param handler: The handler functions to process items.
#    :param destinations: List of tuples (validator, destination).
#    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
#    """
#    put_operations: List[PutOperationPtl[FromDataT]] = [_get_pipe_put_operation_for_handler(
#        handler=handler,
#        destination=destination) for destination in destinations]
#    else:
#        if logger:
#            logger.error("The handlers must match the number of destinations, or there must be only one handler.")
#        raise ValueError("The handlers must match the number of destinations, or there must be only one handler.")
#
#    while True:
#        # Get the next message from the source pipe
#        message: FromDataT = await source.get()
#
#        # The source pipe was stopped and sent the SENTINEL
#        if message is SENTINEL:
#            # Stop the destination pipes
#            tasks: List[Awaitable[None]] = [destination.stop() for destination in destinations]
#            await asyncio.gather(*tasks)
#            source.task_done()
#            break
#
#        # Create a task for each destination pipe
#        tasks: List[Awaitable[None]] = [put_operation(message) for put_operation in put_operations]
#        source.task_done()
#
#        # Run all tasks concurrently
#        await asyncio.gather(*tasks)


async def pipe_to_multipipe_distributor(
        *,
        source: PipeGetPtl[FromDataT],
        handlers: HandlerT | List[HandlerT],
        destinations: List[PipePutPtl[ToDataT]],
        logger: logging.Logger | None = None) -> None:
    """
    Distributes items from a source pipe to multiple destination pipes using a handler function.

    The handler function can be a synchronous function, an asynchronous function,
    a generator function, or an asynchronous generator function.

    If the handler is a generator or async generator, it is expected to yield
    items that will be put into the destination pipes.

    If the handler is a function or async function, it is expected to return
    a single item that will be put into the destination pipes.

    If the task is cancelled, it will stop the destination pipes.

    :param source: The source pipe to get items from.
    :param handlers: The handler functions to process items.
    :param destinations: The destination pipes to put items into.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    """
    if isinstance(handlers, list) and len(handlers) == len(destinations):
        put_operations: List[PutOperationPtl[FromDataT]] = [_get_pipe_put_operation_for_handler(
            handler=handler,
            destination=destination) for handler, destination in zip(handlers, destinations)]
    elif not isinstance(handlers, list) or len(handlers) == 1:
        handler: HandlerT = handlers[0] if isinstance(handlers, list) else handlers
        put_operations: List[PutOperationPtl[FromDataT]] = [_get_pipe_put_operation_for_handler(
            handler=handler,
            destination=destination) for destination in destinations]
    else:
        if logger:
            logger.error("The handlers must match the number of destinations, or there must be only one handler.")
        raise ValueError("The handlers must match the number of destinations, or there must be only one handler.")

    while True:
        # Get the next message from the source pipe
        message: FromDataT = await source.get()

        # The source pipe was stopped and sent the SENTINEL
        if message is SENTINEL:
            # Stop the destination pipes
            tasks: Generator[Coroutine[Any, Any, None]] = (destination.stop() for destination in destinations)
            await asyncio.gather(*tasks)
            source.task_done()
            break

        # Create a task for each destination pipe
        tasks: Generator[Coroutine[Any, Any, None]] = (put_operation(message) for put_operation in put_operations)
        source.task_done()

        # Run all tasks concurrently
        await asyncio.gather(*tasks)


_StreamSourcePtl = StreamMessageIteratorPtl[FromDataT] | StreamSourcePtl[FromDataT]


async def stream_to_pipe_connector(
        *,
        source: _StreamSourcePtl,
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
        raise_on_exception: bool | None = True,
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
    :param raise_on_exception: Whether to raise exceptions that occur while listening to the stream.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    """
    put_operation: Callable[[FromDataT], Awaitable[None]] = _get_pipe_put_operation_for_handler(
        handler=handler,
        destination=destination)

    try:
        if callable(source) and inspect.isawaitable(awaitable := source()):
            source: StreamMessageIteratorPtl[FromDataT] = await awaitable

        async for message in source.iter_messages():  # type: ignore # Pycharm not understanding AsyncGenerator
            try:
                await put_operation(message)
            except PipeFullError:
                log_if_possible(logger, 'warning', "Downstream Pipe is full, retrying 3 times.")
                try:
                    await put_operation(message, wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)
                except PipeFullError as e:
                    log_if_possible(logger, 'warning', "Downstream Pipe full after 3 attempts. Aborting.")
                    raise PipeFullError("Max retries reached, aborting") from e
            # await asyncio.sleep(0)

    except asyncio.CancelledError:
        log_if_possible(logger, 'warning', "Task was cancelled. Closing downstream Pipe")
        await destination.stop()
        raise
    except ConnectionError as e:
        # This is to allow attempts to reconnect on websocket closures
        log_if_possible(logger, 'warning', f"The websocket connection was closed {e}")
    except Exception as e:
        log_if_possible(logger, 'exception', f"Unexpected error while listening to : {e}")
        if raise_on_exception:
            await destination.stop()
            raise e


async def _reconnect_logic(
        connect: Callable[[], Awaitable[None]],
        disconnect: Callable[[], Awaitable[None]],
        interval: float) -> None:
    """Helper function to handle reconnection logic."""
    await disconnect()
    await asyncio.sleep(interval)
    await connect()


async def reconnecting_stream_to_pipe_connector(
        *,
        source: _StreamSourcePtl,
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
        connect: Callable[[], Awaitable[None]],
        disconnect: Callable[[], Awaitable[None]],
        reconnect_interval: float = 5.0,
        logger: logging.Logger | None = None) -> None:
    """
    Auto-ReConnects a source StreamMessageIteratorPtl to a destination pipe using a handler function.
    Calls stream_to_pipe_connector() in a loop.

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
    :param connect: A function that will be called to connect to the source.
    :param disconnect: A function that will be called to disconnect from the source.
    :param reconnect_interval: The time to wait between reconnection attempts.
    :param logger: Optional logger for logging events and exceptions. If not provided, no logging will occur.
    """
    await connect()
    while True:
        try:
            await stream_to_pipe_connector(source=source,
                                           handler=handler,
                                           destination=destination,
                                           raise_on_exception=False,
                                           logger=logger)
        except asyncio.CancelledError as e:
            log_if_possible(logger, 'warning', "Task was cancelled. Closing downstream Pipe")
            await disconnect()
            raise asyncio.CancelledError from e
        except ConnectionError as e:
            log_if_possible(logger, 'warning', f"The websocket connection was closed ({e}). Auto-reconnecting")
            await _reconnect_logic(connect, disconnect, 0)

        except Exception as e:
            log_if_possible(logger, 'error', f"Unexpected error while listening to user stream. ({e})."
                                             f" Auto-reconnect after {reconnect_interval}s")
            await _reconnect_logic(connect, disconnect, reconnect_interval)


def _get_pipe_put_operation_for_handler(
        *,
        handler: HandlerT,
        destination: PipePutPtl[ToDataT],
        on_condition: Callable[[FromDataT | ToDataT], bool] | None = None
) -> PutOperationPtl[FromDataT]:
    """
    Returns an awaitable function that applies the handler to a message and puts
    the result into the destination pipe.

    Note: If the handler function raises an exception, that exception will be propagated
    up to the caller of the returned function. Callers should be prepared to catch and handle
    exceptions raised by the handler.

    :param handler: The handler function to apply to each message.
                 This can be a regular function, a coroutine function,
                 a generator function, or an async generator function.
    :param destination: The destination pipe where the results will be put.
    :param on_condition: An optional function that validates whether the result should be put into the destination.
    :returns: An awaitable function that takes a message, applies the handler to it,
              and puts the result into the destination pipe.
    """

    async def put_if_condition_met(item: FromDataT | ToDataT, **kwargs: Any):
        if on_condition is None or on_condition(item):
            await destination.put(item, **kwargs)

    if handler is None:
        async def put_operation(m: FromDataT, **kwargs: Any):
            await put_if_condition_met(m, **kwargs)

        return put_operation

    if not callable(handler):
        raise TypeError("handler must be a callable function")

    # Check the type of the handler
    is_coroutine = inspect.iscoroutinefunction(handler)
    is_generator = inspect.isgeneratorfunction(handler)
    is_async_generator = inspect.isasyncgenfunction(handler)

    # Define the put operation as an awaitable function
    if is_generator:
        async def put_operation(m: FromDataT, **kwargs: Any):
            for item in handler(m):
                await put_if_condition_met(item, **kwargs)

    elif is_coroutine:
        async def put_operation(m: FromDataT, **kwargs: Any):
            item: ToDataT = await handler(m)
            await put_if_condition_met(item, **kwargs)

    elif is_async_generator:
        async def put_operation(m: FromDataT, **kwargs: Any):
            async for item in handler(m):
                await put_if_condition_met(item, **kwargs)
    else:
        async def put_operation(m: FromDataT, **kwargs: Any):
            item: ToDataT = handler(m)
            await put_if_condition_met(item, **kwargs)

    return put_operation
