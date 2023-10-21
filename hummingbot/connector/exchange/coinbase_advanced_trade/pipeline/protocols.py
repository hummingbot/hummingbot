from typing import AsyncGenerator, Awaitable, Protocol, runtime_checkable

from ..pipe.data_types import DataT


class StreamMessageIteratorPtl(Protocol[DataT]):
    """
    A protocol for an iterator that can be used to get items from a stream.
    """

    async def iter_messages(self) -> AsyncGenerator[DataT, None]:
        """Gets an item from the stream or blocks until an item is available."""
        ...

    async def connect(self) -> Awaitable[None]:
        """Connects to the stream."""
        ...

    async def disconnect(self) -> Awaitable[None]:
        """Disconnects from the stream."""
        ...


@runtime_checkable
class StreamSourcePtl(Protocol[DataT]):
    """
    A protocol as a prototype for a stream source.
    """

    async def __call__(self) -> StreamMessageIteratorPtl[DataT]:
        ...
