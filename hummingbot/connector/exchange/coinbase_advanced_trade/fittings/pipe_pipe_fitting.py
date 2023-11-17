import functools
import logging

from hummingbot.logger import HummingbotLogger

from ..connecting_functions import pipe_to_pipe_connector
from ..pipe.data_types import FromDataT, HandlerT, PipeDataT, PipeTupleDataT, ToDataT
from ..pipe.protocols import PipeGetPtl
from ..pipeline.data_types import DestinationT
from ..pipeline.pipeline_base import PipelineBase
from .data_types import ConnectToPipeTaskT


class PipePipeFitting(PipelineBase[FromDataT, ToDataT]):
    """
    A PipePipeFitting is a PipelineBase that connects a Pipe source to a Pipe destination with
    an optional handler in between, using a pipe_to_pipe_connector.
    """

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = (
        "_source"
    )

    def __init__(
            self,
            source: PipeGetPtl[FromDataT],
            handler: HandlerT | None = None,
            destination: DestinationT | None = None,
            logger: HummingbotLogger | logging.Logger | None = None,
    ):
        self._source: PipeGetPtl[FromDataT] = source

        connecting_task: ConnectToPipeTaskT = functools.partial(
            pipe_to_pipe_connector,
            logger=logger or self.logger(),
        )
        super().__init__(
            source=source,
            handler=handler,
            destination=destination,
            connecting_task=connecting_task)

    async def get(self) -> PipeDataT:
        return await self._source.get()

    def task_done(self) -> None:
        return self._source.task_done()

    async def snapshot(self) -> PipeTupleDataT:
        return await self._source.snapshot()

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the PipePipeFitting:\n"
                            f" {ex}")
