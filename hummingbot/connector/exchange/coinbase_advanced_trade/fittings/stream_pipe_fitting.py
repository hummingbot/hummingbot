import functools
import logging

from hummingbot.logger import HummingbotLogger

from ..connecting_functions import stream_to_pipe_connector
from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipeline.data_types import DestinationT
from ..pipeline.pipeline_base import PipelineBase
from ..pipeline.protocols import StreamMessageIteratorPtl, StreamSourcePtl
from .data_types import ConnectToPipeTaskT


class StreamPipeFitting(PipelineBase[FromDataT, ToDataT]):
    """
    A StreamPipeFitting is a PipelineBase that connects a StreamMessageIterator to
    a Pipe destination with an optional handler in between, using a
    stream_to_pipe_connector.
    """

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = ()

    def __init__(
            self,
            *,
            source: StreamMessageIteratorPtl[FromDataT] | StreamSourcePtl[FromDataT],
            handler: HandlerT | None = None,
            destination: DestinationT | None = None,
            logger: HummingbotLogger | logging.Logger | None = None,
    ):
        connecting_task: ConnectToPipeTaskT = functools.partial(
            stream_to_pipe_connector,
            logger=logger or self.logger(),
        )
        super().__init__(source=source,
                         handler=handler,
                         destination=destination,
                         connecting_task=connecting_task)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the StreamPipeFitting:\n"
                            f" {ex}")
