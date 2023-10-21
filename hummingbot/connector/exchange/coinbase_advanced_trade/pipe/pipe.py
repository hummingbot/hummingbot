import asyncio
import contextlib
import logging
from logging import Logger
from typing import Generic, List, Type

from hummingbot.logger import HummingbotLogger

from .data_types import DataT, PipeDataT, PipeTupleDataT
from .errors import PipeFullError, PipeSentinelError, PipeStoppedError
from .protocols import PipeGetPtl, PipePutPtl
from .sentinel import SENTINEL


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
        "_snapshot_lock",
    )

    def __init__(self,
                 maxsize: int = 0,
                 pipe: Type[_PipePtl[DataT]] = asyncio.Queue[DataT],
                 release_to_loop: bool = True) -> None:
        self._pipe: _PipePtl[DataT] = pipe(maxsize=max(maxsize, 0))

        self._is_stopped: bool = False
        self._release_to_loop: bool = release_to_loop
        self._sentinel_position: int = -1
        self._snapshot_lock: asyncio.Lock = asyncio.Lock()
        self._space_available = asyncio.Condition()

    @property
    def pipe(self) -> _PipePtl[DataT]:
        return self._pipe

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

    async def _attempt_put_or_wait(self, item: PipeDataT, delay: float) -> bool:
        """
        Attempts to put an item into the pipe. On failure, waits for the specified delay.
        This is a private method and should only be used internally by the Pipe class.

        :param item: The item to put into the queue
        :param delay: The delay between retries
        :return: True if the item was put into the queue, False otherwise
        """
        try:
            await self._wait_for_snapshot_to_finish()
            self._pipe.put_nowait(item)
            return True
        except asyncio.QueueFull:
            self.logger().debug(f"Pipe is full - Retrying in {delay}s")
            await asyncio.sleep(delay)
            return False

    async def put(
            self,
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

        await self._put_exponential_wait(
            item,
            wait_time=wait_time,
            max_retries=max_retries,
            max_wait_time_per_retry=max_wait_time_per_retry)

        if self._release_to_loop:
            # This allows the event loop to switch to other tasks
            # Doing so should help propagate the message
            await asyncio.sleep(0)

    async def _put_exponential_wait(
            self,
            item: PipeDataT,
            *,
            wait_time: float = 0,
            max_retries: int = 0,
            max_wait_time_per_retry: float = 10) -> None:
        """
        Puts an item into the pipe with exponential wait.

        :param item: The item to put into the queue
        :param wait_time: The timeout to wait for the queue to be available
        :param max_retries: The maximum number of retries to put the item into the queue
        :param max_wait_time_per_retry: The maximum wait time between retries (exponential backoff can go crazy)
        """
        # This allows to test if the queue has been stopped rather than blocking
        retries: int = 0
        while not self._is_stopped and retries <= abs(max_retries):
            geometric_wait: float = (wait_time * 1000.0) ** retries / 1000.0
            delay: float = min(retries * geometric_wait, abs(max_wait_time_per_retry))
            if await self._attempt_put_or_wait(item, delay):
                break
            retries += 1

        if retries == max_retries + 1:
            self.logger().error(f"Failed to put item after {retries} attempts")
            raise PipeFullError("Failed to put item into the pipe after maximum retries")

        if self._release_to_loop:
            # This allows the event loop to switch to other tasks
            # Doing so should help propagate the message
            await asyncio.sleep(0)

    async def _put_on_condition(self, item: PipeDataT) -> None:
        async with self._space_available:
            while self._pipe.full():
                await self._space_available.wait()
            self._pipe.put_nowait(item)

        if self._release_to_loop:
            # This allows the event loop to switch to other tasks
            # Doing so should help propagate the message
            await asyncio.sleep(0)

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
            self._pipe.task_done()
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
            self._pipe.task_done()

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
            self._pipe.task_done()

        async with self._space_available:
            self._space_available.notify()
        return item

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
                            self._pipe.task_done()
                        break

            return tuple(snapshot)
