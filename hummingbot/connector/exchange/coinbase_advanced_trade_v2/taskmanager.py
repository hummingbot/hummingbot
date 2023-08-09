import asyncio
import contextlib
import logging
from asyncio import Task
from functools import partial
from typing import Any, Awaitable, Callable, Optional, Protocol

from hummingbot.logger import HummingbotLogger


class TaskManagerError(Exception):
    pass


class TaskManagerPtl(Protocol):
    def start_task(self) -> None:
        ...

    def stop_task(self) -> None:
        ...


class TaskManager:
    """Task manager handling the details of starting/stopping tasks"""

    _logger: Optional[HummingbotLogger | logging.Logger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(HummingbotLogger.logger_name_for_class(cls))
        return cls._logger

    __slots__ = (
        "_awaitable",
        "_task",
        "_task_exception",
        "_success_callback",
        "_exception_callback",
        "_success_event",
        "_exception_event",
    )

    def __init__(
            self,
            task: Callable[..., Awaitable[Any]],
            *args,
            success_callback: Optional[Callable[[], None]] = None,
            exception_callback: Optional[Callable[[Exception], None]] = None,
            success_event: Optional[asyncio.Event] = None,
            exception_event: Optional[asyncio.Event] = None,
            **kwargs):
        self._success_callback: Optional[Callable[[], None]] = success_callback
        self._exception_callback: Optional[Callable[[Exception], None]] = exception_callback
        self._success_event: Optional[asyncio.Event] = success_event
        self._exception_event: Optional[asyncio.Event] = exception_event

        self._awaitable: Callable[..., Awaitable[Any]] = partial(task, *args, **kwargs)

        self._task: Optional[Task] = None
        self._task_exception: Optional[Exception] = None

    @property
    def task(self) -> Optional[Task]:
        return self._task

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def task_exception(self) -> Exception:
        return self._task_exception

    async def start_task(self) -> None:
        """Starts the queue processor."""
        if self._task and not self._task.done():
            self.logger().error("Cannot start a Task Manager that is already started")
            return

        async def task_wrapper() -> None:
            try:
                await self._awaitable()
            except Exception as ex:
                self._task_exception = ex
                if self._exception_callback is not None:
                    self._exception_callback(ex)
                if self._exception_event is not None:
                    self._exception_event.set()
            else:
                if self._success_callback is not None:
                    self._success_callback()
                if self._success_event is not None:
                    self._success_event.set()
                self._task = None

        if not self._task or self._task.done():
            try:
                self._task: Task = asyncio.create_task(task_wrapper())
            except Exception as e:
                self.logger().error(f"Exception while creating task: {e}")
                raise e

    def _log_and_raise_task_exception(self) -> None:
        """Logs and raises the _task_exception if it exists and no exception callback is provided."""
        if self._task_exception is not None:
            self.logger().error(f"Task raised an exception: {self._task_exception}")
            if self._exception_callback is None:
                raise self._task_exception
            self.logger().warning("The exception was not raised because an exception callback was provided")

    async def stop_task(self) -> None:
        """Stops the queue processor."""
        if not self._task or self._task.done():
            self.logger().error("Attempting to stop() a task that has not been created (or already stopped)")
            return

        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

        self._log_and_raise_task_exception()

    def stop_task_nowait(self) -> None:
        """Stops the task without waiting for it to complete."""
        if not self._task or self._task.done():
            self.logger().error("Attempting to stop() a task that has not been created (or already stopped)")
            return

        self._task.cancel()

        self._log_and_raise_task_exception()
        self.logger().warning("The task cancellation was requested, however, the task may still be running.")
