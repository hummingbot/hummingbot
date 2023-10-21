from typing import Any, AsyncGenerator, Protocol, runtime_checkable

from .data_types import DataT, FromDataT, PipeDataT, PipeTupleDataT


class PipeGetPtl(Protocol[DataT]):
    """
    A protocol for a Pipe that can be used to get items from the Pipe.
    """
    async def get(self) -> PipeDataT:
        """
        Gets an item from the Pipe. If the Pipe is empty it blocks until an item is available.
        """
        ...

    def empty(self) -> bool:
        """
        Returns True if the Pipe is empty.
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

    def size(self) -> int:
        """
        Returns the number of items in the Pipe.
        """
        ...

    async def snapshot(self) -> PipeTupleDataT:
        """
        Returns a snapshot of the Pipe as a tuple of (items,).
        """
        ...


class PipePutPtl(Protocol[DataT]):
    """
    A protocol for a Pipe that can be used to put items into the Pipe.
    """
    async def put(self, item: PipeDataT, **kwargs) -> None:
        """
        Puts an item into the Pipe. If the Pipe is full it blocks until space is available.
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


class PutOperationPtl(Protocol[FromDataT]):
    """
    A protocol for a PutOperation that can be used to put items into the Pipe.
    """
    async def __call__(self, item: FromDataT, **kwargs: Any) -> None:
        ...


class StreamMessageIteratorPtl(Protocol[DataT]):
    """
    A protocol for an iterator that can be used to get items from a stream.
    """
    async def iter_messages(self) -> AsyncGenerator[DataT, None]:
        ...


@runtime_checkable
class StreamSourcePtl(Protocol[DataT]):
    """
    A protocol as a prototype for a stream source.
    """
    async def __call__(self) -> StreamMessageIteratorPtl[DataT]:
        ...
