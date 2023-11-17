import functools
import logging
from typing import Awaitable, Callable

from hummingbot.logger import HummingbotLogger

from ..connecting_functions import reconnecting_stream_to_pipe_connector
from ..connecting_functions.exception_log_manager import log_exception
from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipeline.data_types import DestinationT
from ..pipeline.pipeline_base import PipelineBase
from ..pipeline.protocols import StreamMessageIteratorPtl, StreamSourcePtl
from .data_types import ReConnectToPipeTaskT


class AutoStreamPipeFitting(PipelineBase[FromDataT, ToDataT]):
    """
    A StreamPipeFitting is a PipelineBase that connects a StreamMessageIterator to a Pipe destination.
    """

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = ()

    def __init__(self,
                 source: StreamMessageIteratorPtl[FromDataT] | StreamSourcePtl[FromDataT],
                 connect: Callable[..., Awaitable[None]],
                 disconnect: Callable[..., Awaitable[None]],
                 reconnect_interval: float = 1.0,
                 max_reconnect_attempts: int = 3,
                 handler: HandlerT | None = None,
                 destination: DestinationT | None = None,
                 logger: logging.Logger | None = None):

        # Define the connecting task
        connecting_task: ReConnectToPipeTaskT = functools.partial(
            reconnecting_stream_to_pipe_connector,
            reconnect_interval=reconnect_interval,
            max_reconnect_attempts=max_reconnect_attempts,
            logger=logger or self.logger())

        super().__init__(
            source=source,
            handler=handler,
            destination=destination,
            connecting_task=connecting_task,
            connect=connect,
            disconnect=disconnect)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        log_exception(
            ex,
            self.logger(),
            "ERROR",
            "An error occurred while executing the task in the AutoStreamPipeFitting.")
