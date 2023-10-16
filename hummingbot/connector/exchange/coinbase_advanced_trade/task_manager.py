import asyncio
import contextlib
import logging
from asyncio import Task
from enum import Enum
from typing import Any, Awaitable, Callable

from hummingbot.logger import HummingbotLogger


class TaskState(Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    STOPPED = "STOPPED"


class TaskManager:
    """
    A wrapper class for asyncio tasks that provides logging and exception handling.
    """

    _logger: HummingbotLogger | logging.Logger | None = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = (
        "_awaitable",
        "_task",
        "_task_exception",
        "_task_state",
        "_success_callback",
        "_exception_callback",
        "_success_event",
        "_exception_event",
    )

    def __init__(
            self,
            task: Callable[..., Awaitable[Any]],
            *args,
            success_callback: Callable[[], None] | None = None,
            exception_callback: Callable[[Exception], None] | None = None,
            success_event: asyncio.Event | None = None,
            exception_event: asyncio.Event | None = None,
            **kwargs):
        self._success_callback: Callable[[], None] | None = success_callback
        self._exception_callback: Callable[[Exception], None] | None = exception_callback
        self._success_event: asyncio.Event | None = success_event
        self._exception_event: asyncio.Event | None = exception_event

        self._awaitable: Awaitable[Any] = task(*args, **kwargs)

        self._task: Task | None = None
        self._task_exception: Exception | None = None
        self._task_state: TaskState = TaskState.STOPPED

    @property
    def task_exception(self) -> Exception | None:
        """Returns the exception raised by the task, if any."""
        return self._task_exception

    @property
    def is_running(self) -> bool:
        """Returns True if the queue processor is running."""
        return self._task and not self._task.done()

    async def start_task(self) -> None:
        """Starts the queue processor."""
        if self.is_running:
            self.logger().debug("Cannot start_task() a Task Manager that is already started")
            return
        self._task: Task = asyncio.create_task(self._task_wrapper())
        self._task_state = TaskState.CREATED

    async def _task_wrapper(self) -> None:
        """Wraps the task in a try/except block to catch any exceptions."""
        self._task_state = TaskState.STARTED
        try:
            await self._awaitable
        except Exception as ex:
            self._task_exception = ex
            self._exception_callback(ex) if self._exception_callback else None
            self._exception_event.set() if self._exception_event else None
        else:
            self._success_callback() if self._success_callback else None
            self._success_event.set() if self._success_event else None
        finally:
            self._task_state = TaskState.STOPPED
            self._task = None

    async def stop_task(self) -> None:
        """Stops the queue processor."""
        if not self.is_running:
            self.logger().debug("Attempting to stop_task() a task that has not been created (or already stopped)")
            return

        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None
        self._task_state = TaskState.STOPPED

    def stop_task_nowait(self) -> None:
        """Stops the task without waiting for it to complete."""
        if not self.is_running:
            self.logger().debug("Attempting to stop_task_nowait() a task that has not been created (or already stopped)")
            return

        self._task.cancel()
        self._task_state = TaskState.STOPPED
