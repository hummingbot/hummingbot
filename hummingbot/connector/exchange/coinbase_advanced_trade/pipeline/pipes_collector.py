import asyncio
import logging
from typing import Generic, Tuple

from hummingbot.logger import HummingbotLogger

from ..pipe.data_types import FromDataT, HandlerT, ToDataT
from ..pipe.pipe import Pipe
from ..pipe.protocols import PipeGetPtl
from .connecting_functions import pipe_to_pipe_connector
from .data_types import ConnectToPipeTaskT, DestinationT, ReConnectToPipeTaskT
from .pipe_block import PipeBlock
from .pipeline_block import _default_handler


class PipesCollector(Generic[FromDataT, ToDataT]):
    """
    A block that connects several Pipe sources to a Pipe destination.
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
                 destination: DestinationT | None = None,
                 connecting_task: ConnectToPipeTaskT | ReConnectToPipeTaskT = pipe_to_pipe_connector):
        if handler is None:
            handler = _default_handler

        # Record the destination to be the source for the next block
        if destination is None:
            destination = Pipe[ToDataT]()
        self.destination: DestinationT = destination

        self._pipe_blocks: Tuple[PipeBlock[FromDataT, ToDataT], ...] = tuple(
            PipeBlock[FromDataT, ToDataT](
                source=s,
                handler=handler,
                destination=self.destination,
                connecting_task=connecting_task
            )
            for s in sources
        )
        self._update_lock: asyncio.Lock = asyncio.Lock()

    async def start_all_tasks(self) -> None:
        """Start all the collecting tasks."""
        await asyncio.gather(*(p.start_task() for p in self._pipe_blocks))

    async def stop_all_tasks(self) -> None:
        """Stop all the collecting tasks."""
        await asyncio.gather(*[p.stop_task() for p in self._pipe_blocks])

    async def start_task(self, pipe: PipeBlock[FromDataT, ToDataT]) -> None:
        """Start the task associated with a pipe."""
        if pipe in self._pipe_blocks and not pipe.is_running:
            await pipe.start_task()

    async def stop_task(self, pipe: PipeBlock[FromDataT, ToDataT]) -> None:
        """Stop the task associated with a pipe."""
        if pipe in self._pipe_blocks and pipe.is_running:
            await pipe.stop_task()

    async def remove_source(self, source: PipeBlock[FromDataT, ToDataT]) -> None:
        """Stop the task."""
        if source in self._pipe_blocks:
            if source.is_running:
                await source.stop_task()
            async with self._update_lock:
                self._pipe_blocks = tuple(p for p in self._pipe_blocks if p != source)

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
