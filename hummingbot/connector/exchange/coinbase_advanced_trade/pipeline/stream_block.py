from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from .connecting_functions import stream_to_pipe_connector
from .data_types import ConnectToPipeTaskT, DestinationT, ReConnectToPipeTaskT
from .pipeline_block import PipelineBlock
from .protocols import StreamMessageIteratorPtl, StreamSourcePtl


class StreamBlock(PipelineBlock[FromDataT, ToDataT]):
    """
    A StreamBlock is a PipelineBlock that connects a StreamMessageIterator to a Pipe destination.
    """

    __slots__ = ()

    def __init__(self,
                 source: StreamMessageIteratorPtl[FromDataT] | StreamSourcePtl[FromDataT],
                 handler: HandlerT | None = None,
                 destination: DestinationT | None = None,
                 connecting_task: ConnectToPipeTaskT | ReConnectToPipeTaskT = stream_to_pipe_connector):
        super().__init__(source=source,
                         handler=handler,
                         destination=destination,
                         connecting_task=connecting_task)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the StreamBlock:\n"
                            f" {ex}")
