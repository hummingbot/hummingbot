import asyncio
import contextlib
import logging
from asyncio import Task
from enum import Enum
from typing import Any, Awaitable, Callable

from hummingbot.logger import HummingbotLogger
from hummingbot.logger.indenting_logger import indented_debug_decorator


class TaskState(Enum):
    CREATED = "CREATED"
    STARTED = "STARTED"
    STOPPED = "STOPPED"


class TaskManagerException(Exception):
    pass


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
        "__task_function",
        "_task",
        "_task_args",
        "_task_kwargs",
        "_task_exception",
        "_task_state",
        "_success_callback",
        "_exception_callback",
        "_success_event",
        "_exception_event",
    )

    @indented_debug_decorator(msg="TaskManager", bullet=":")
    def __init__(
            self,
            task_function: Callable[[...], Awaitable[Any]],
            *args: Any,
            success_callback: Callable[[], None] | None = None,
            exception_callback: Callable[[Exception], None] | None = None,
            success_event: asyncio.Event | None = None,
            exception_event: asyncio.Event | None = None,
            **kwargs: Any,
    ):
        """
        :param task_function: The function to be run as a Task
        :param success_callback: A callback function to be called when the task completes successfully
        :param exception_callback: A callback function to be called when the task raises an exception
        :param success_event: An event to be set when the task completes successfully
        :param exception_event: An event to be set when the task raises an exception
        """
        if not callable(task_function):
            raise TypeError("task_function must be a callable function")

        self._success_callback: Callable[[], None] | None = success_callback
        self._exception_callback: Callable[[Exception], None] | None = exception_callback
        self._success_event: asyncio.Event | None = success_event
        self._exception_event: asyncio.Event | None = exception_event

        self.__task_function: Callable[[...], Awaitable[Any]] = task_function
        self._task_args: Any = args
        self._task_kwargs: Any = kwargs

        self._task: Task | None = None
        self._task_exception: TaskManagerException | None = None
        self._task_state: TaskState = TaskState.STOPPED

    @property
    def task_function(self) -> Callable[[...], Awaitable[Any]]:
        """Returns the awaitable that is being run by the task."""
        return self.__task_function

    @property
    def task(self) -> Task | None:
        """Returns the task."""
        return self._task

    @property
    def task_exception(self) -> Exception | None:
        """Returns the exception raised by the task, if any."""
        return self._task_exception

    @property
    def task_state(self) -> TaskState:
        """Returns the current state of the task."""
        return self._task_state

    @property
    def is_running(self) -> bool:
        """Returns True if the task is running."""
        return self._task is not None and not self._task.done()

    @property
    def is_done(self) -> bool:
        """Returns True if the has run and is done."""
        return self._task is not None and self._task.done()

    # @indented_debug_decorator(msg="start_task", bullet=">")
    def start_task(self) -> None:
        """Starts the queue processor."""
        if self.is_running:
            self.logger().debug("Cannot start_task() a Task Manager that is already started")
            return
        if self.is_done:
            self.logger().debug("This task has been completed. Please create a new Task Manager.")
            return
        self._task: Task = asyncio.create_task(self._task_wrapper())
        self._task_state = TaskState.CREATED
        # await asyncio.sleep(0)

    async def _task_wrapper(self) -> None:
        """Wraps the task in a try/except block to catch any exceptions."""
        self._task_state = TaskState.STARTED
        try:
            await self.__task_function(*self._task_args, **self._task_kwargs)
        except Exception as ex:
            self._task_exception = TaskManagerException(
                f"An error occurred while executing the task {self.task}\n"
                f" in the TaskManager:\n {ex}")
            self._exception_callback(ex) if self._exception_callback is not None else None
            self._exception_event.set() if self._exception_event is not None else None
        else:
            self._success_callback() if self._success_callback is not None else None
            self._success_event.set() if self._success_event is not None else None
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
            self.logger().debug(
                "Attempting to stop_task_nowait() a task that has not been created (or already stopped)")
            return

        self._task.cancel()
        self._task_state = TaskState.STOPPED
