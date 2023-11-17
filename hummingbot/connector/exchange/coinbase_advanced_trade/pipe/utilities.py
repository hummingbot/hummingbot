import logging

from ..connecting_functions.exception_log_manager import log_exception
from .data_types import DataT, FromDataT, FromTupleDataT, PipeTupleDataT, ToDataT
from .errors import PipeFullError, PipeTypeError
from .protocols import PipeGetPtl, PipePutPtl, PutOperationPtl
from .sentinel import sentinel_ize


async def pipe_snapshot(pipe: PipeGetPtl[DataT]) -> PipeTupleDataT:
    """
    Returns a snapshot of the queue.
    """
    if not hasattr(pipe, "snapshot"):
        raise PipeTypeError("pipe argument must provide a snapshot() method")
    return await getattr(pipe, "snapshot")()


async def process_residual_data_on_cancel(
        source: PipeGetPtl[FromDataT],
        put_operation: PutOperationPtl[FromDataT],
        destination: PipePutPtl[ToDataT],
        logger: logging.Logger | None = None) -> None:
    """
    Helper function to process residual data on cancellation of a task.
    """
    messages: FromTupleDataT = sentinel_ize(await pipe_snapshot(source))
    try:
        [await put_operation(m) for m in messages[:-1]]
    except PipeFullError as e:
        log_exception(e,
                      logger,
                      'ERROR',
                      "Data loss: Attempted to flush upstream Pipe on cancellation, however, "
                      "downstream Pipe is full.")
    await destination.stop()
