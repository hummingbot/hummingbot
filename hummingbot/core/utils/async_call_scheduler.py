import asyncio
import logging
from typing import Any, Callable, Coroutine, NamedTuple, Optional

from async_timeout import timeout

import hummingbot
from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class AsyncCallSchedulerItem(NamedTuple):
    """
    A named tuple representing an item in the AsyncCallScheduler's coroutine queue.

    :param future: The asyncio.Future object representing the result of the coroutine.
    :param coroutine: The coroutine to be executed by the scheduler.
    :param timeout_seconds: The number of seconds before the coroutine times out.
    :param app_warning_msg: A custom warning message to be logged in case of an error during coroutine execution.
    """
    future: asyncio.Future
    coroutine: Coroutine
    timeout_seconds: float
    app_warning_msg: str = "API call error."


class AsyncCallScheduler:
    """
    A class that schedules asynchronous calls with a configurable interval and timeout.

    It provides an interface to schedule coroutines or regular functions and supports
    handling timeouts and errors.
    """
    _acs_shared_instance: Optional["AsyncCallScheduler"] = None
    _acs_logger: Optional[HummingbotLogger] = None

    @classmethod
    def shared_instance(cls) -> "AsyncCallScheduler":
        """
        Get the shared instance of the AsyncCallScheduler. If it doesn't exist, create a new one.

        :return: The shared instance of the AsyncCallScheduler.
        """
        if cls._acs_shared_instance is None:
            cls._acs_shared_instance = AsyncCallScheduler()
        return cls._acs_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        """
        Get the logger instance for the AsyncCallScheduler.

        :return: The logger instance for the AsyncCallScheduler.
        """
        if cls._acs_logger is None:
            cls._acs_logger = logging.getLogger(__name__)
        return cls._acs_logger

    def __init__(self, call_interval: float = 0.01):
        """
        Initialize a new instance of the AsyncCallScheduler.

        :param call_interval: The interval between calls, in seconds.
        """
        self._coro_scheduler_task: Optional[asyncio.Task] = None
        self._call_interval: float = call_interval
        self._coro_queue: asyncio.Queue = asyncio.Queue()

    @property
    def coro_queue(self) -> asyncio.Queue:
        """
        Get the coroutine queue of the AsyncCallScheduler.

        :return: The coroutine queue of the AsyncCallScheduler.
        """
        return self._coro_queue

    @property
    def coro_scheduler_task(self) -> Optional[asyncio.Task]:
        """
        Get the current task running the coroutine scheduler.

        :return: The current task running the coroutine scheduler, or None if not running.
        """
        return self._coro_scheduler_task

    @property
    def started(self) -> bool:
        """
        Check if the AsyncCallScheduler is started.

        :return: True if started, False otherwise.
        """
        return self._coro_scheduler_task is not None

    def start(self) -> None:
        """
        Start the AsyncCallScheduler.

        If it is already running, stop it first and then start it again.
        """
        if self._coro_scheduler_task is not None:
            self.stop()
        self._coro_scheduler_task = safe_ensure_future(
            self._coro_scheduler(
                self._coro_queue,
                self._call_interval
            )
        )

    def stop(self) -> None:
        """
        Stop the AsyncCallScheduler.

        Cancel the running coroutine scheduler task if it exists.
        """
        if self._coro_scheduler_task is not None:
            self._coro_scheduler_task.cancel()
            self._coro_scheduler_task = None

    async def _coro_scheduler(self, coro_queue: asyncio.Queue, interval: float = 0.01) -> None:
        """
        Coroutine scheduler.

        This method continuously processes coroutines from the given coroutine queue and
        executes them with the specified timeout. It sleeps for a given interval between
        processing coroutines if the queue is empty.

        :param coro_queue: The asyncio.Queue containing coroutines to be executed.
        :param interval: The interval between coroutine executions, in seconds, when the queue is empty.
        """

        async def process_coroutine() -> None:
            """
            Dequeue and process a coroutine from the coro_queue.

            This function attempts to execute the coroutine with the given timeout.
            It handles various exceptions that may occur during the execution.
            """
            item = await coro_queue.get()
            fut, coro, timeout_seconds, app_warning_msg = item

            try:
                async with timeout(timeout_seconds):
                    fut.set_result(await coro)
            except asyncio.CancelledError:  # The timeout expired
                fut.cancel()
                raise
            except asyncio.InvalidStateError:  # The future is already done
                pass
            except Exception as e:
                handle_generic_exception(e, fut, app_warning_msg)

        def handle_generic_exception(e: Exception, fut: asyncio.Future, app_warning_msg: str) -> None:
            """
            Handle generic exceptions.

            This function logs the exception and sets it as the result of the future object.

            :param e: The exception that occurred.
            :param fut: The future object to set the exception on.
            :param app_warning_msg: A warning message to include in the log.
            """
            app_warning_msg += f" [[Got exception: {str(e)}]]"
            self.logger().debug(app_warning_msg, exc_info=True, extra={"app_warning_msg": app_warning_msg})
            try:
                fut.set_exception(e)
            except Exception:
                pass

        while True:
            await process_coroutine()

            if coro_queue.empty():
                try:
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self.logger().error("Scheduler sleep interrupted.", exc_info=True)

    async def schedule_async_call(self,
                                  coro: Coroutine,
                                  timeout_seconds: float,
                                  app_warning_msg: str = "API call error.") -> Any:
        """
        Schedule a coroutine for execution with a specified timeout.

        :param coro: The coroutine to be executed.
        :param timeout_seconds: The number of seconds before the coroutine times out.
        :param app_warning_msg: A custom warning message to be logged in case of an error during coroutine execution.
        :return: The result of the coroutine execution.
        """
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._coro_queue.put_nowait(AsyncCallSchedulerItem(future=fut,
                                                           coroutine=coro,
                                                           timeout_seconds=timeout_seconds,
                                                           app_warning_msg=app_warning_msg))
        if self._coro_scheduler_task is None:
            self.start()
        return await fut

    async def call_async(self,
                         func: Callable,
                         *args,
                         timeout_seconds: float = 5.0,
                         app_warning_msg: str = "API call error.") -> Any:
        """
        Schedule a regular function for asynchronous execution with a specified timeout.

        :param func: The function to be executed.
        :param args: The arguments to be passed to the function.
        :param timeout_seconds: The number of seconds before the function execution times out.
        :param app_warning_msg: A custom warning message to be logged in case of an error during function execution.
        :return: The result of the function execution.
        """
        async def async_func(*args):
            future = asyncio.get_event_loop().run_in_executor(hummingbot.get_executor(), func, *args)
            return await future
        coro: Coroutine = async_func(*args)
        return await self.schedule_async_call(coro, timeout_seconds, app_warning_msg=app_warning_msg)
