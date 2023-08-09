import asyncio
import contextlib
import inspect
import logging
from logging import Logger
from types import UnionType
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Generic,
    List,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    runtime_checkable,
)

from hummingbot.logger import HummingbotLogger


class Sentinel:
    pass


# Create an instance of the sentinel
SENTINEL = Sentinel()

DataT = TypeVar("DataT")

PipeDataT = DataT | Sentinel
PipeTupleDataT = Tuple[PipeDataT, ...]


class _PipePtl(Generic[DataT]):
    def __init__(self, maxsize: int) -> None:
        ...

    async def get(self) -> PipeDataT:
        ...

    def get_nowait(self) -> PipeDataT:
        ...

    def empty(self) -> bool:
        ...

    def task_done(self) -> None:
        ...

    async def join(self) -> None:
        ...

    async def put(self, item: PipeDataT) -> None:
        ...

    def put_nowait(self, item: PipeDataT) -> None:
        ...

    def full(self) -> bool:
        ...

    def qsize(self) -> int:
        ...


class PipeGetPtl(Protocol[DataT]):
    async def get(self) -> PipeDataT:
        ...

    def empty(self) -> bool:
        ...

    def task_done(self) -> None:
        ...

    async def join(self) -> None:
        ...

    def size(self) -> int:
        ...

    async def snapshot(self) -> PipeTupleDataT:
        ...


class PipePutPtl(Protocol[DataT]):
    async def put(self, item: PipeDataT, **kwargs) -> None:
        ...

    def full(self) -> bool:
        ...

    async def stop(self) -> None:
        ...


class PipeStoppedError(Exception):
    """Raised when an attempt is made to get an item from a stopped Pipe."""
    pass


class PipeFullError(Exception):
    """Raised when an attempt is made to put an item in a full Pipe."""
    pass


class PipeSentinelError(Exception):
    """Raised when an exception occurs related to the SENTINEL of Pipe."""
    pass


class PipeTypeError(Exception):
    """Raised when an exception occurs related to the Pipe structure."""
    pass


class Pipe(Generic[DataT], PipeGetPtl[DataT], PipePutPtl[DataT]):
    """
    A node in the pipeline that has a queue and recognizes a SENTINEL value to stop the pipeline.
    """
    _logger: HummingbotLogger | Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger | Logger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = (
        "_pipe",
        "_is_stopped",
        "_release_to_loop",
        "_sentinel_position",
        "_snapshot_in_progress",
    )

    def __init__(self,
                 maxsize: int = 0,
                 pipe: Type[_PipePtl[DataT]] = asyncio.Queue[DataT],
                 release_to_loop: bool = True) -> None:
        self._pipe: _PipePtl[DataT] = pipe(maxsize=max(maxsize, 0))

        self._is_stopped: bool = False
        self._release_to_loop: bool = release_to_loop
        self._sentinel_position: int = -1
        self._snapshot_in_progress: bool = False

    @property
    def pipe(self) -> _PipePtl[DataT]:
        return self._pipe

    @property
    def snapshot_in_progress(self) -> bool:
        return self._snapshot_in_progress

    @snapshot_in_progress.setter
    def snapshot_in_progress(self, value: bool) -> None:
        self._snapshot_in_progress = value

    @property
    def is_stopped(self) -> bool:
        return self._is_stopped

    @property
    def size(self) -> int:
        return self._pipe.qsize()

    async def _put_sentinel(self) -> None:
        """
        Puts a SENTINEL into the pipe.
        This is a private method and should only be used internally by the Pipe class.
        """
        await self._pipe.put(SENTINEL)

    async def put(self,
                  item: PipeDataT,
                  *,
                  wait_time: float = 0,
                  max_retries: int = 0,
                  max_wait_time_per_retry: float = 10) -> None:
        """
        Puts an item into the pipe.

        :param item: The item to put into the queue
        :param wait_time: The timeout to wait for the queue to be available
        :param max_retries: The maximum number of retries to put the item into the queue
        :param max_wait_time_per_retry: The maximum wait time between retries (exponential backoff can go crazy)
        """
        if self._is_stopped:
            raise PipeStoppedError("Cannot put item into a stopped Pipe")

        if item is SENTINEL:
            raise PipeSentinelError("The SENTINEL cannot be inserted in the Pipe")

        if self._snapshot_in_progress:
            while self._snapshot_in_progress:
                await asyncio.sleep(0)

        # This allows to test if the queue has been stopped rather than blocking
        retries: int = 0
        while not self._is_stopped and retries <= abs(max_retries):
            try:
                self._pipe.put_nowait(item)
                break
            except asyncio.QueueFull:
                delay: float = min(retries * (wait_time * 1000.0) ** retries / 1000.0,
                                   abs(max_wait_time_per_retry))
                self.logger().debug(f"Pipe is full {retries} / {max_retries} - "
                                    f"Retrying in {delay}s")
                retries += 1
                await asyncio.sleep(delay)

        if retries == max_retries + 1:
            self.logger().error(f"Failed to put item after {retries} attempts")
            raise PipeFullError("Failed to put item into the pipe after maximum retries")

        if self._release_to_loop:
            # This allows the event loop to switch to other tasks
            # Doing so should help propagate the message
            await asyncio.sleep(0)

    async def _get_internally(self) -> PipeDataT:
        """
        Returns the next item from the queue.
        Private method intended to be called by the get() method or snapshot() method.
        """
        if self._sentinel_position == 0:
            # The queue was stopped while full (SENTINEL not inserted)
            # and is now empty: resets the position and returns the SENTINEL
            self._sentinel_position = -1
            return SENTINEL

        if self._sentinel_position > 0:
            # The queue was stopped while full (SENTINEL not inserted)
            # and is not yet empty - The queue could have received new items
            # since the stop() call, but this implementation will ignore them
            self._sentinel_position = self._sentinel_position - 1

        try:
            # Attempting to get an item
            # If the queue is empty, this will raise an exception
            return self._pipe.get_nowait()
        except asyncio.QueueEmpty:
            if not self._snapshot_in_progress:
                return await self._pipe.get()

    async def get(self) -> PipeDataT:
        """
        Returns the next item from the queue. Awaits if a snapshot is underway
        Awaits for an item it the queue is empty.
        """
        while self._snapshot_in_progress:
            await asyncio.sleep(0)

        return await self._get_internally()

    def task_done(self) -> None:
        """
        Signals that the item returned by the last call to `get` has been processed.
        """
        self._pipe.task_done()

    async def join(self) -> None:
        """
        Blocks until all items in the queue have been processed.
        """
        await self._pipe.join()

    async def stop(self) -> None:
        """
        Signals that no more items will be put in the queue, but the SENTINEL
        """
        if not self._is_stopped:
            self._is_stopped = True
            if self._pipe.full():
                self._sentinel_position = self._pipe.qsize()
            else:
                self._sentinel_position = -1
                await self._put_sentinel()

            if self._release_to_loop:
                # This allows the event loop to switch to other tasks
                # Doing so should help propagate the stop signal
                await asyncio.sleep(0)

    async def snapshot(self) -> PipeTupleDataT:
        """
        Returns a snapshot of the queue. This method empties the queue
        """
        self._snapshot_in_progress = True

        snapshot: List[PipeDataT] = []
        with contextlib.suppress(asyncio.QueueEmpty):
            while not self._pipe.empty():
                item: DataT = await self._get_internally()
                snapshot.append(item)
                if item is SENTINEL:
                    # This should not be needed, but in the rare case where an item is put
                    # in the queue between the last get_nowait() and the stop() call, we
                    # want to make sure the queue is empty before returning the snapshot.
                    # so the task_done() can be used to enable the join() call.
                    while not self._pipe.empty():
                        _ = self._pipe.get_nowait()
                    break
        self._pipe.snapshot_in_progress = False

        return tuple(snapshot)

    @classmethod
    async def pipe_snapshot(cls, pipe: PipeGetPtl[DataT]) -> PipeTupleDataT:
        """
        Returns a snapshot of the queue.
        """
        if not issubclass(Pipe, cls):
            raise PipeTypeError(f"pipe argument must be an instance of {cls.__name__}, not {type(pipe).__name__}")
        if not hasattr(pipe, "snapshot"):
            raise PipeTypeError("pipe argument must provide a snapshot() method")
        return await getattr(pipe, "snapshot")()

    @staticmethod
    def sentinel_ize(items: PipeTupleDataT) -> PipeTupleDataT:
        """
        Returns a tuple with a sentinel value at the end. If a sentinel value is already present in the tuple,
        it returns a new tuple up to the first sentinel. If no sentinel is present, it adds one to the end of the tuple.

        :param items: A tuple of items, which may include a sentinel value.
        :return: A tuple with a sentinel value at the end.
        :raises ValueError: If there are multiple sentinel values in the tuple.
        """
        try:
            sentinel_index = items.index(SENTINEL)
            return items[:sentinel_index + 1]
        except ValueError:
            return items + (SENTINEL,)


# --- Pipe Connectors ---

async def pipe_to_async_generator(pipe: PipeGetPtl[DataT]) -> AsyncGenerator[DataT, None]:
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


class PipeAsyncIterator(Generic[DataT]):
    """
    An async iterator that iterates over a Pipe. It can be stopped by calling
    the `stop` method.
    """

    __slots__ = (
        "_pipe",
    )

    def __init__(self, pipe: PipeGetPtl[DataT]) -> None:
        self._pipe: PipeGetPtl[DataT] = pipe

    def __aiter__(self) -> AsyncIterator[DataT]:
        return self

    async def __anext__(self) -> DataT:
        """
        Returns the next item from the queue. If the Pipe has been stopped it signals
        the end of the iteration.
        """
        try:
            item = await self._pipe.get()
            if item is SENTINEL:
                raise StopAsyncIteration
            return item
        except asyncio.CancelledError as e:
            raise StopAsyncIteration from e
        except Exception as e:
            raise e


# --- PipeTaskManager associated to the Pipe class ---


FromDataT = TypeVar("FromDataT")
ToDataT = TypeVar("ToDataT")
FromTupleDataT = Tuple[FromDataT | Sentinel, ...]

_SyncTransformerT: Type = Callable[[FromDataT], ToDataT]
_AsyncTransformerT: Type = Callable[[FromDataT], Awaitable[ToDataT]]
_SyncComposerT: Type = Callable[[FromDataT], Generator[ToDataT, None, None]]
_AsyncDecomposerT: Type = Callable[[FromDataT], AsyncGenerator[ToDataT, None]]

HandlerT: UnionType = _SyncTransformerT | _AsyncTransformerT | _SyncComposerT | _AsyncDecomposerT


class PutOperationPtl(Protocol[FromDataT]):
    async def __call__(self, item: FromDataT, **kwargs: Any) -> None:
        ...


def _get_pipe_put_operation_for_handler(
        *,
        handler: HandlerT,
        destination: PipePutPtl[ToDataT]) -> PutOperationPtl[FromDataT]:
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
    :returns: An awaitable function that takes a message, applies the handler to it,
              and puts the result into the destination pipe.
    """

    if handler is None:
        async def put_operation(m: FromDataT, **kwargs: Any):
            await destination.put(m, **kwargs)

        return put_operation

    # Check the type of the handler
    is_coroutine = inspect.iscoroutinefunction(handler)
    is_generator = inspect.isgeneratorfunction(handler)
    is_async_generator = inspect.isasyncgenfunction(handler)

    # Define the put operation as an awaitable function
    if is_generator:
        async def put_operation(m: FromDataT, **kwargs: Any):
            for item in handler(m):
                await destination.put(item, **kwargs)
    elif is_coroutine:
        async def put_operation(m: FromDataT, **kwargs: Any):
            await destination.put(await handler(m), **kwargs)
    elif is_async_generator:
        async def put_operation(m: FromDataT, **kwargs: Any):
            async for item in handler(m):
                await destination.put(item, **kwargs)
    else:
        async def put_operation(m: FromDataT, **kwargs: Any):
            await destination.put(handler(m), **kwargs)

    return put_operation


def log_if_possible(logger: logging.Logger | None, level: str, message: str, exc_info: bool = False):
    """
    Logs a message if a logger is provided.

    :param logger: The logger to use for logging.
    :param level: The level of the log message ('info', 'warning', 'error', etc.).
    :param message: The message to log.
    :param exc_info: Whether to include exception information in the log.
    """
    if logger:
        log_func = getattr(logger, level)
        log_func(message, exc_info=exc_info)


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

    while True:
        try:
            message: FromDataT | Sentinel = await source.get()

            # The source pipe was stopped and sent the SENTINEL
            if message is SENTINEL:
                # Stop the destination pipe in turn
                await destination.stop()
                source.task_done()
                break

            try:
                await put_operation(message)
            except PipeFullError:
                log_if_possible(logger, 'warning', "Downstream Pipe is full, retrying with .")
                await put_operation(message, wait_time=0.1, max_retries=3, max_wait_time_per_retry=1)

            source.task_done()
            await asyncio.sleep(0)

        # Task is cancelled
        except asyncio.CancelledError:
            log_if_possible(logger, 'warning', "Task was cancelled. Attempting to process remaining items.")
            messages: FromTupleDataT = await Pipe[FromDataT].pipe_snapshot(source)
            messages: FromTupleDataT = Pipe[FromDataT].sentinel_ize(messages)
            for message in messages[:-1]:
                try:
                    await put_operation(message)
                    source.task_done()
                    await asyncio.sleep(0)
                except PipeFullError:
                    log_if_possible(logger, 'error', "Attempted to flush upstream Pipe on cancellation, however, "
                                                     "downstream Pipe is full. Loss of data incurred.")
                    break
            await destination.stop()
            break
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
    """
    # Create a task for each source
    tasks = [
        pipe_to_pipe_connector(source=source, handler=handler, destination=destination, logger=logger)
        for source in sources
    ]

    # Run all tasks concurrently
    await asyncio.gather(*tasks)


async def pipe_to_multipipe_distributor(
        *,
        source: PipeGetPtl[FromDataT],
        handlers: HandlerT | List[HandlerT],
        destinations: List[PipePutPtl[ToDataT]],
        logger: logging.Logger | None = None) -> None:
    """
    Distributes items from a source pipe to multiple destination pipes using a handler function.
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
        raise ValueError("The handlers must match the number of destinations, or there must be only one handler.")

    while True:
        # Get the next message from the source pipe
        message: FromDataT = await source.get()

        # The source pipe was stopped and sent the SENTINEL
        if message is SENTINEL:
            # Stop the destination pipes
            tasks: List[Awaitable[None]] = [destination.stop() for destination in destinations]
            await asyncio.gather(*tasks)
            source.task_done()
            break

        # Create a task for each destination pipe
        tasks: List[Awaitable[None]] = [put_operation(message) for put_operation in put_operations]
        source.task_done()

        # Run all tasks concurrently
        await asyncio.gather(*tasks)


class StreamMessageIteratorPtl(Protocol[DataT]):
    async def iter_messages(self) -> AsyncGenerator[DataT, None]:
        ...


@runtime_checkable
class StreamSourcePtl(Protocol[DataT]):
    async def __call__(self) -> StreamMessageIteratorPtl[DataT]:
        ...


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
        if callable(source) and inspect.isawaitable(source):
            source: StreamMessageIteratorPtl[FromDataT] = await source()

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
            await asyncio.sleep(0)

    except asyncio.CancelledError:
        log_if_possible(logger, 'warning', "Task was cancelled. Closing downstream Pipe")
        await destination.stop()
    except ConnectionError as e:
        # This is to allow attempts to reconnect on websocket closures
        log_if_possible(logger, 'warning', f"The websocket connection was closed {e}")
    except Exception as e:
        log_if_possible(logger, 'exception', f"Unexpected error while listening to : {e}")
        if raise_on_exception:
            await destination.stop()
            raise e


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
    while True:
        try:
            await connect()
            await stream_to_pipe_connector(source=source,
                                           handler=handler,
                                           destination=destination,
                                           raise_on_exception=False,
                                           logger=logger)
        except asyncio.CancelledError:
            log_if_possible(logger, 'warning', "Task was cancelled. Closing downstream Pipe")
            await disconnect()
            raise
        except ConnectionError as e:
            log_if_possible(logger, 'warning', f"The websocket connection was closed ({e}). Auto-reconnecting")
        except Exception as e:
            log_if_possible(logger, 'error', f"Unexpected error while listening to user stream. ({e})."
                                             f" Auto-reconnect after {reconnect_interval}s")
            await asyncio.sleep(reconnect_interval)
        finally:
            await disconnect()

# --- PipeConnectors associated to the Pipe class and its Pipe task manager ---
