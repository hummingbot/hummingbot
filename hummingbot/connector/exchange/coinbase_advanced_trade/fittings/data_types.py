import logging
from typing import Any, Awaitable, Callable, Coroutine

from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.protocols import PipeGetPtl, PipePutPtl
from ..pipeline.protocols import StreamMessageIteratorPtl

ConnectToPipeTaskT = Callable[
    [
        Any,  # This specifies that we restrict to keyword arguments
        PipeGetPtl[FromDataT] | StreamMessageIteratorPtl[FromDataT],
        HandlerT,
        PipePutPtl[ToDataT],
        logging.Logger | None,
        Callable[..., Awaitable[None]] | None,
        Callable[..., Awaitable[None]] | None,
    ],
    Coroutine[Any, Any, None]
]
ReConnectToPipeTaskT = Callable[
    [
        Any,  # This specifies that we restrict to keyword arguments
        PipeGetPtl[FromDataT] | StreamMessageIteratorPtl[FromDataT],
        HandlerT,
        PipePutPtl[ToDataT],
        Callable[..., Awaitable[None]],
        Callable[..., Awaitable[None]],
        float,
        logging.Logger | None,
    ],
    Coroutine[Any, Any, None]
]
