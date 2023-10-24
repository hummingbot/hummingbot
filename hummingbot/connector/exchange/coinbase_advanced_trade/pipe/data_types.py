from types import UnionType
from typing import AsyncGenerator, Awaitable, Callable, Generator, Tuple, Type, TypeVar

from .sentinel import Sentinel

DataT = TypeVar("DataT")
PipeDataT = DataT | Sentinel
PipeTupleDataT = Tuple[PipeDataT, ...]
FromDataT = TypeVar("FromDataT")
ToDataT = TypeVar("ToDataT")
FromTupleDataT = Tuple[FromDataT | Sentinel, ...]

_SyncTransformerT: Type = Callable[[FromDataT], ToDataT]
_AsyncTransformerT: Type = Callable[[FromDataT], Awaitable[ToDataT]]
_SyncComposerT: Type = Callable[[FromDataT], Generator[ToDataT, None, None]]
_AsyncComposerT: Type = Callable[[FromDataT], AsyncGenerator[ToDataT, None]]
HandlerT: UnionType = _SyncTransformerT | _AsyncTransformerT | _SyncComposerT | _AsyncComposerT

_SyncSplitterT: Type = Callable[[FromDataT], Tuple[ToDataT, ...]]
_AsyncSplitterT: Type = Callable[[FromDataT], Awaitable[ToDataT]]
_SyncComposerT: Type = Callable[[FromDataT], Generator[ToDataT, None, None]]
_AsyncComposerT: Type = Callable[[FromDataT], AsyncGenerator[ToDataT, None]]
