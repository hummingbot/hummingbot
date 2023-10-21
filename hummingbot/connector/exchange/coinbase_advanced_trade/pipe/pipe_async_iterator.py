import asyncio
from typing import AsyncIterator, Generic

from .data_types import DataT
from .protocols import PipeGetPtl
from .sentinel import SENTINEL


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
