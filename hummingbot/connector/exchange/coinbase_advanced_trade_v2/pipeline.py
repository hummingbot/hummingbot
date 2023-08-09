import asyncio
import logging
from typing import Any, Awaitable, Callable, Coroutine, Dict, Generic, Protocol, Tuple, TypeVar

from hummingbot.connector.exchange.coinbase_advanced_trade_v2.pipe import (
    HandlerT,
    Pipe,
    PipeGetPtl,
    PipePutPtl,
    StreamMessageIteratorPtl,
    StreamSourcePtl,
    pipe_to_pipe_connector,
    reconnecting_stream_to_pipe_connector,
    stream_to_pipe_connector,
)
from hummingbot.connector.exchange.coinbase_advanced_trade_v2.taskmanager import TaskManager
from hummingbot.logger import HummingbotLogger

FromDataT = TypeVar("FromDataT")
ToDataT = TypeVar("ToDataT")

_DestinationPtl = StreamMessageIteratorPtl[ToDataT] | PipePutPtl[ToDataT] | PipeGetPtl[ToDataT]

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


def _default_handler(message: FromDataT) -> ToDataT:
    return message


class _HasDataPtl(Protocol):
    data: Any


class PipelineBlock(Generic[FromDataT, ToDataT]):
    """
    A PipelineBlock is a TaskManager that connects a source to a destination.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = ("destination",
                 "task_manager"
                 )

    def __init__(self,
                 *,
                 source: PipeGetPtl[FromDataT] | StreamSourcePtl,
                 handler: HandlerT | None = _default_handler,
                 destination: _DestinationPtl | None = Pipe[ToDataT](),
                 connecting_task: ConnectToPipeTaskT | ReConnectToPipeTaskT,
                 connect: Callable[..., Awaitable[None]] | None = None,
                 disconnect: Callable[..., Awaitable[None]] | None = None, ):
        """
        Initialize a PipelineBlock.

        :param source: The source of data.
        :param handler: The function to handle data. If None, a default handler is used that does not change the data.
        :param destination: The destination to put the handled data. If None, a new Pipe is created.
        :param connecting_task: The task that connects the source and destination.
        """
        # If no handler is specified, use the default handler
        if handler is None:
            handler = _default_handler

        # Record the destination to be the source for the next block
        if destination is None:
            destination = Pipe[ToDataT]()
        self.destination: _DestinationPtl = destination

        task_args: Dict[str, Any] = {"source": source, "destination": destination, "handler": handler}
        if connect is not None:
            task_args["connect"] = connect
        if disconnect is not None:
            task_args["disconnect"] = disconnect

        # Create the connecting task
        self.task_manager: TaskManager = TaskManager(connecting_task, **task_args,
                                                     exception_callback=self.task_exception_callback)

    async def start_task(self) -> None:
        """Start the task."""
        await self.task_manager.start_task()

    async def stop_task(self) -> None:
        """Stop the task."""
        await self.task_manager.stop_task()

    @property
    def is_running(self) -> bool:
        """Stop the task."""
        return self.task_manager.is_running

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the PipelineBlock:\n"
                            f" {ex}")
        # self.stop_task()
        # If necessary, you can re-raise the exception, handle it in some other way, or just log it and continue
        # For example, to re-raise the exception, uncomment the following line:
        # raise ex


class StreamBlock(PipelineBlock[FromDataT, ToDataT]):
    """
    A StreamBlock is a PipelineBlock that connects a StreamMessageIterator to a Pipe destination.
    """

    def __init__(self,
                 source: StreamMessageIteratorPtl[FromDataT] | StreamSourcePtl[FromDataT],
                 handler: HandlerT | None = None,
                 destination: _DestinationPtl | None = None):
        super().__init__(source=source,
                         handler=handler,
                         destination=destination,
                         connecting_task=stream_to_pipe_connector)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the StreamBlock:\n"
                            f" {ex}")


class AutoStreamBlock(PipelineBlock[FromDataT, ToDataT]):
    """
    A StreamBlock is a PipelineBlock that connects a StreamMessageIterator to a Pipe destination.
    """

    def __init__(self,
                 source: StreamMessageIteratorPtl[FromDataT] | StreamSourcePtl[FromDataT],
                 connect: Callable[..., Awaitable[None]],
                 disconnect: Callable[..., Awaitable[None]],
                 handler: HandlerT | None = None,
                 destination: _DestinationPtl | None = None):
        super().__init__(
            source=source,
            handler=handler,
            destination=destination,
            connecting_task=reconnecting_stream_to_pipe_connector,
            connect=connect,
            disconnect=disconnect)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the AutoStreamBlock:\n"
                            f" {ex}")


class PipeBlock(PipelineBlock[FromDataT, ToDataT]):
    """
    A PipeBlock is a PipelineBlock that connects a Pipe source to a Pipe destination.
    """

    def __init__(self,
                 source: PipeGetPtl[FromDataT],
                 handler: HandlerT | None = None,
                 destination: _DestinationPtl | None = None):
        setattr(self, "get", getattr(source, "get", None))
        setattr(self, "snapshot", getattr(source, "snapshot", None))

        super().__init__(
            source=source,
            handler=handler,
            destination=destination,
            connecting_task=pipe_to_pipe_connector)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the PipeBlock:\n"
                            f" {ex}")


class PipesCollector(Generic[FromDataT, ToDataT]):
    """
    A PipeBlock is a PipelineBlock that connects a Pipe source to a Pipe destination.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(self,
                 sources: Tuple[PipeGetPtl[FromDataT]],
                 handler: HandlerT | None = None,
                 destination: _DestinationPtl | None = None):
        if handler is None:
            handler = _default_handler

        # Record the destination to be the source for the next block
        if destination is None:
            destination = Pipe[ToDataT]()
        self.destination: _DestinationPtl = destination

        self._pipe_blocks: Tuple[PipeBlock[FromDataT, ToDataT], ...] = tuple(
            PipeBlock[FromDataT, ToDataT](
                source=s,
                handler=handler,
                destination=self.destination
            )
            for s in sources
        )

    async def start_task(self) -> None:
        """Start the task."""
        await asyncio.gather(*(p.start_task() for p in self._pipe_blocks))

    async def stop_task(self) -> None:
        """Stop the task."""
        await asyncio.gather(*[p.stop_task() for p in self._pipe_blocks])

    @property
    def are_running(self) -> Tuple[bool, ...]:
        """Tuple of running status of each pipe block."""
        return tuple(p.is_running for p in self._pipe_blocks)

    @property
    def all_running(self) -> bool:
        """Tuple of running status of each pipe block."""
        return all(p.is_running for p in self._pipe_blocks)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        self.logger().error("An error occurred while executing the task in the PipesCollector:\n"
                            f" {ex}")
