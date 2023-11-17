import logging
from typing import Any, Awaitable, Callable, Dict, Generic, Protocol

from hummingbot.logger import HummingbotLogger
from hummingbot.logger.indenting_logger import indented_debug_decorator

from ..connecting_functions import pipe_to_pipe_connector
from ..fittings.data_types import ConnectToPipeTaskT, ReConnectToPipeTaskT
from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.pipe import Pipe
from ..pipe.protocols import PipeGetPtl
from ..task_manager import TaskManager
from .data_types import DestinationT
from .protocols import StreamSourcePtl


def pass_message_through_handler(message: FromDataT) -> ToDataT:
    return message


class _HasDataPtl(Protocol):
    data: Any


class PipelineBase(Generic[FromDataT, ToDataT]):
    """
    A PipelineBase is a TaskManager that connects a source to a destination.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = (
        "destination",
        "task_manager"
    )

    @indented_debug_decorator(msg="PipelineBase.__init__", bullet=":")
    def __init__(
            self,
            *,
            source: PipeGetPtl[FromDataT] | StreamSourcePtl,
            handler: HandlerT | None = pass_message_through_handler,
            destination: DestinationT | None = Pipe[ToDataT](),
            connecting_task: ConnectToPipeTaskT | ReConnectToPipeTaskT = pipe_to_pipe_connector,
            connect: Callable[..., Awaitable[None]] | None = None,
            disconnect: Callable[..., Awaitable[None]] | None = None,
    ):
        """
        Initialize a PipelineBase.

        :param source: The source of data.
        :param handler: The function to handle data. If None, a default handler is used that does not change the data.
        :param destination: The destination to put the handled data. If None, a new Pipe is created.
        :param connect: A function to connect to the source. If None, the source is assumed to be already connected.
        :param disconnect: A function to disconnect from the source. If None, the source is assumed to be already
                             disconnected.
        """
        # If no handler is specified, use the default handler
        if handler is None:
            handler = pass_message_through_handler

        # Record the destination to be the source for the next block
        if destination is None:
            destination = Pipe[ToDataT]()
        self.destination: DestinationT = destination

        task_args: Dict[str, Any] = {"source": source, "destination": destination, "handler": handler}
        if connect is not None:
            task_args["connect"] = connect
        if disconnect is not None:
            task_args["disconnect"] = disconnect

        # Create the connecting task
        self.task_manager: TaskManager = TaskManager(
            connecting_task,
            **task_args,
            exception_callback=self.task_exception_callback)

    def start_task(self) -> None:
        """Start the task."""
        self.task_manager.start_task()

    async def stop_task(self) -> None:
        """Stop the task."""
        await self.task_manager.stop_task()

    def is_running(self) -> bool:
        """Stop the task."""
        return self.task_manager.is_running

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the PipelineBase:\n"
                            f"    {ex}")
        # self.stop_all_tasks()
        # If necessary, you can re-raise the exception, handle it in some other way, or just log it and continue
        # For example, to re-raise the exception, uncomment the following line:
        # raise ex
