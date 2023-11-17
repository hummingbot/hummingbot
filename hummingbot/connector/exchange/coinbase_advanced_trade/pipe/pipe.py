import asyncio
import contextlib
import logging
from logging import Logger
from typing import Generic, List, Protocol, Type

from hummingbot.logger import HummingbotLogger
from hummingbot.logger.indenting_logger import indented_debug_decorator

from .data_types import DataT, PipeDataT, PipeTupleDataT
from .errors import PipeFullError, PipeSentinelError, PipeStoppedError
from .protocols import PipePtl
from .sentinel import SENTINEL


class _PipeBasePtl(Protocol[DataT]):
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


class Pipe(Generic[DataT], PipePtl[DataT]):
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
        "_perform_task_done",
        "_sentinel_position",
        "_snapshot_lock",
        "_space_available",
    )

    @indented_debug_decorator(msg="Pipe.__init__", bullet=":")
    def __init__(self,
                 maxsize: int = 0,
                 pipe: Type[_PipeBasePtl[DataT]] = asyncio.Queue[DataT],
                 perform_task_done: bool = True) -> None:
        self._pipe: _PipeBasePtl[DataT] = pipe(maxsize=max(maxsize, 0))

        self._is_stopped: bool = False
        self._perform_task_done: bool = perform_task_done
        self._sentinel_position: int = -1
        self._snapshot_lock: asyncio.Lock = asyncio.Lock()
        self._space_available = asyncio.Condition()

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

    async def put(
            self,
            item: PipeDataT,
            *,
            timeout: float = 1) -> None:
        """
        Puts an item into the pipe.

        :param item: The item to put into the queue
        :param timeout: The timeout to wait for the queue to be available
        :raises PipeFullError: If the item cannot be put into the queue after the maximum number of retries
        :raises PipeSentinelError: If the SENTINEL is put into the queue
        :raises PipeStoppedError: If the queue is stopped
        """
        if self._is_stopped:
            raise PipeStoppedError("Cannot put item into a stopped Pipe")

        if item is SENTINEL:
            raise PipeSentinelError("The SENTINEL cannot be inserted in the Pipe")

        await self._put_on_condition(item, timeout=timeout)

    async def _put_on_condition(self, item: PipeDataT, timeout: float | None = None) -> None:
        """
        Puts an item into the pipe.

        :param item: The item to put into the queue.
        :raises asyncio.TimeoutError: If the pipe is full and the timeout is reached.

        Explanation: This method puts an item into the pipe. It first acquires the `_space_available` lock to ensure
        exclusive access to the pipe. If the pipe is full, it waits until space becomes available by using the
        `_space_available.wait()` method. If the timeout is reached while waiting for space to become available,
        it raises an `asyncio.TimeoutError`. Once space is available, it puts the item into the pipe using the
        `put_nowait()` method. If `_release_to_loop` is True, it allows the event loop to switch to other tasks by
        sleeping for a short duration.
        """
        async with self._space_available:
            while self._pipe.full():
                try:
                    await asyncio.wait_for(self._space_available.wait(), timeout=timeout)
                except asyncio.TimeoutError as e:
                    self.logger().error(f"Failed to put item after {timeout} seconds")
                    raise PipeFullError("Pipe is full and timeout reached") from e
            self._pipe.put_nowait(item)

    def _get_internally_no_lock(self) -> PipeDataT:
        """
        Returns the next item from the queue.
        Calls task_done() on the queue when an item is returned.
        Private method intended to be called by the get() method or snapshot() method.

        :raises asyncio.QueueEmpty: If the queue is empty
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
            item: PipeDataT = self._pipe.get_nowait()
            self._pipe.task_done() if self._perform_task_done else None
            return item
        except asyncio.QueueEmpty:
            raise

    async def get(self) -> PipeDataT:
        """
        Returns the next item from the queue. Awaits if a snapshot is underway
        Awaits for an item it the queue is empty.
        """
        await self._wait_for_snapshot_to_finish()

        try:
            item: PipeDataT = self._get_internally_no_lock()
        except asyncio.QueueEmpty:
            item: PipeDataT = await self._pipe.get()
            self._pipe.task_done() if self._perform_task_done else None

        return item

    async def _get_on_condition(self) -> PipeDataT:
        """
        Returns the next item from the queue. Awaits if a snapshot is underway
        Awaits for an item it the queue is empty.
        """
        await self._wait_for_snapshot_to_finish()

        try:
            item: PipeDataT = self._get_internally_no_lock()
        except asyncio.QueueEmpty:
            item: PipeDataT = await self._pipe.get()
            self._pipe.task_done() if self._perform_task_done else None

        async with self._space_available:
            self._space_available.notify()
        return item

    async def join(self) -> None:
        """
        Blocks until all items in the queue have been processed.
        """
        await self._pipe.join()

    def task_done(self) -> None:
        """
        Accounts for the processing of an element obtained by get()
        """
        None if self._perform_task_done else self._pipe.task_done()

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

    async def _wait_for_snapshot_to_finish(self):
        """Waits for the snapshot to finish."""
        if self._snapshot_lock.locked():
            async with self._snapshot_lock:
                pass

    async def snapshot(self) -> PipeTupleDataT:
        """
        This code defines an asynchronous method snapshot that returns a snapshot of a queue.
        The method empties the queue and returns a tuple containing the items in the queue up
        to the sentinel value (SENTINEL).
        """
        async with self._snapshot_lock:
            snapshot: List[PipeDataT] = []
            with contextlib.suppress(asyncio.QueueEmpty):
                while not self._pipe.empty():
                    # We simply want to empty till the SENTINEL
                    with contextlib.suppress(asyncio.QueueEmpty):
                        item: DataT = self._get_internally_no_lock()
                    snapshot.append(item) if item is not None else None
                    if item is SENTINEL:
                        # This should not be needed, but in the rare case where an item is put
                        # in the queue between the last get_nowait() and the stop() call, we
                        # want to make sure the queue is empty before returning the snapshot.
                        # so the task_done() can be used to enable the join() call.
                        while not self._pipe.empty():
                            _ = self._pipe.get_nowait()
                            self._pipe.task_done() if self._perform_task_done else None
                        break

            return tuple(snapshot)
