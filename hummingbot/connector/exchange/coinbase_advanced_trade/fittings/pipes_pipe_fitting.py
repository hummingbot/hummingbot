import asyncio
import logging
from typing import Generic, Tuple

from hummingbot.logger import HummingbotLogger

from ..connecting_functions.exception_log_manager import log_exception
from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.pipe import Pipe
from ..pipe.protocols import PipeGetPtl
from ..pipeline.data_types import DestinationT
from ..pipeline.pipeline_base import pass_message_through_handler
from .pipe_pipe_fitting import PipePipeFitting


class PipesPipeFitting(Generic[FromDataT, ToDataT]):
    """
    A block that connects several Pipe sources to a Pipe destination
    with an optional handler in between, using a pipe_to_pipe_connector.
    """
    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger: HummingbotLogger | logging.Logger = logging.getLogger(
                HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    def __init__(
            self,
            *,
            sources: Tuple[PipeGetPtl[FromDataT], ...],
            handler: HandlerT | None = None,
            destination: DestinationT | None = None,
            logger: HummingbotLogger | logging.Logger | None = None,
    ):
        """
        Initialize a PipesPipeFitting.

        :param sources: The sources of data.
        :param handler: The function to handle data. If None, a default handler is used that does not change the data.
        :param destination: The destination to put the handled data. If None, a new Pipe is created.
        """
        if handler is None:
            handler = pass_message_through_handler

        # Record the destination to be the source for the next block
        if destination is None:
            destination = Pipe[ToDataT]()
        self.destination: DestinationT = destination

        self._pipe_pipe: Tuple[PipePipeFitting[FromDataT, ToDataT], ...] = tuple(
            PipePipeFitting[FromDataT, ToDataT](
                source=s,
                handler=handler,
                destination=self.destination,
                logger=logger or self.logger(),
            )
            for s in sources
        )
        self._update_lock: asyncio.Lock = asyncio.Lock()

    async def start_all_tasks(self) -> None:
        """Start all the collecting tasks."""
        await asyncio.gather(*[p.start_task() for p in self._pipe_pipe if not p.is_running()])

    async def stop_all_tasks(self) -> None:
        """Stop all the collecting tasks."""
        await asyncio.gather(*[p.stop_task() for p in self._pipe_pipe if p.is_running()])

    def stop_all_tasks_nowait(self) -> None:
        """Stop all the collecting tasks."""
        [p.stop_task_nowait() for p in self._pipe_pipe if p.is_running()]

    async def stop_task(self, pipe: PipePipeFitting[FromDataT, ToDataT]) -> None:
        """Stop the task associated with a pipe."""
        if pipe in self._pipe_pipe and pipe.is_running:
            await pipe.stop_task()

    async def remove_source(self, source: PipePipeFitting[FromDataT, ToDataT]) -> None:
        """Stop the task."""
        if source in self._pipe_pipe:
            if source.is_running:
                await source.stop_task()
            async with self._update_lock:
                self._pipe_pipe = tuple(p for p in self._pipe_pipe if p != source)

    def are_running(self) -> Tuple[bool, ...]:
        """Tuple of running status of each pipe block."""
        return tuple(p.is_running() for p in self._pipe_pipe)

    def all_running(self) -> bool:
        """Tuple of running status of each pipe block."""
        return all(p.is_running() for p in self._pipe_pipe)

    def task_exception_callback(self, ex: Exception) -> None:
        """Handle an exception raised during the execution of the task."""
        # Log the exception
        log_exception(ex, self.logger(), "ERROR")
