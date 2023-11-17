from typing import Callable, Tuple

from ..pipe.data_types import ToDataT
from ..pipe.protocols import PipeGetPtl, PipePutPtl
from .protocols import StreamMessageIteratorPtl

DestinationT = StreamMessageIteratorPtl[ToDataT] | PipePutPtl[ToDataT] | PipeGetPtl[ToDataT]
ConditionalDestinationT = Tuple[DestinationT, Callable[[ToDataT], bool]]
