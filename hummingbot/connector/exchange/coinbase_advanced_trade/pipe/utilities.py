import logging

from .data_types import DataT, PipeTupleDataT
from .errors import PipeTypeError
from .protocols import PipeGetPtl


async def pipe_snapshot(pipe: PipeGetPtl[DataT]) -> PipeTupleDataT:
    """
    Returns a snapshot of the queue.
    """
    if not hasattr(pipe, "snapshot"):
        raise PipeTypeError("pipe argument must provide a snapshot() method")
    return await getattr(pipe, "snapshot")()


def log_if_possible(logger: logging.Logger | None, level: str, message: str, exc_info: bool = False):
    """
    Logs a message if a logger is provided.

    :param logger: The logger to use for logging.
    :param level: The level of the log message ('info', 'warning', 'error', etc.).
    :param message: The message to log.
    :param exc_info: Whether to include exception information in the log.
    """
    if logger:
        log_func = getattr(logger, level)
        log_func(message, exc_info=exc_info)
