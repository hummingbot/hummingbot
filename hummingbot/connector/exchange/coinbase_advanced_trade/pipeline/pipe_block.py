from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.protocols import PipeGetPtl
from .connecting_functions import pipe_to_pipe_connector
from .data_types import ConnectToPipeTaskT, DestinationT, ReConnectToPipeTaskT
from .pipeline_block import PipelineBlock


class PipeBlock(PipelineBlock[FromDataT, ToDataT]):
    """
    A PipeBlock is a PipelineBlock that connects a Pipe source to a Pipe destination.
    """

    def __init__(self,
                 source: PipeGetPtl[FromDataT],
                 handler: HandlerT | None = None,
                 destination: DestinationT | None = None,
                 connecting_task: ConnectToPipeTaskT | ReConnectToPipeTaskT = pipe_to_pipe_connector):
        setattr(self, "get", getattr(source, "get", None))
        setattr(self, "snapshot", getattr(source, "snapshot", None))
        setattr(self, "task_done", getattr(source, "task_done", None))

        super().__init__(
            source=source,
            handler=handler,
            destination=destination,
            connecting_task=connecting_task)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the PipeBlock:\n"
                            f" {ex}")
