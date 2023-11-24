from typing import Any, Protocol, runtime_checkable

from .data_types import DataT, FromDataT, PipeDataT, PipeTupleDataT


@runtime_checkable
class PipeGetPtl(Protocol[DataT]):
    """
    A protocol for a Pipe that can be used to get items from the Pipe.
    """
    __slots__ = ()

    @property
    def size(self) -> int:
        return ...

    async def get(self) -> PipeDataT:
        """
        Gets an item from the Pipe. If the Pipe is empty it blocks until an item is available.
        """
        ...

    def task_done(self) -> None:
        """
        Signals that an item that was gotten from the Pipe has been processed.
        """
        ...

    async def join(self) -> None:
        """
        Blocks until all items in the Pipe have been processed.
        """
        ...

    async def snapshot(self) -> PipeTupleDataT:
        """
        Returns a snapshot of the Pipe as a tuple of (items,).
        """
        ...


@runtime_checkable
class PipePutPtl(Protocol[DataT]):
    """
    A protocol for a Pipe that can be used to put items into the Pipe.
    """
    __slots__ = ()

    async def put(self, item: PipeDataT, *, timeout: float = 10) -> None:
        """
        Puts an item into the pipe.

        :param item: The item to put into the queue
        :param timeout: The maximum number of seconds to wait for the queue to accept the item
        :raises PipeFullError: If the item cannot be put into the queue after the maximum number of retries
        :raises PipeSentinelError: If the SENTINEL is put into the queue
        :raises PipeStoppedError: If the queue is stopped
        """
        ...

    def full(self) -> bool:
        """
        Returns True if the Pipe is full.
        """
        ...

    async def stop(self) -> None:
        """
        Stops the Pipe.
        """
        ...

    async def start(self) -> None:
        """
        Starts. Flushes the Pipe.
        """
        ...


@runtime_checkable
class PipePtl(PipeGetPtl[DataT], PipePutPtl[DataT], Protocol[DataT]):
    """
    A node in the pipeline that has a queue and recognizes a SENTINEL value to stop the pipeline.
    """
    __slots__ = ()

    @property
    def is_stopped(self) -> bool:
        return ...


@runtime_checkable
class PutOperationPtl(Protocol[FromDataT]):
    """
    A protocol for a PutOperation that can be used to put items into the Pipe.
    """

    async def __call__(self, item: FromDataT, **kwargs: Any) -> None:
        ...
