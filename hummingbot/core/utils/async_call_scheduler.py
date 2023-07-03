import asyncio
import logging
from asyncio import Future, Queue, Task
from typing import Any, Coroutine, NamedTuple, Protocol, TypeVar

from async_timeout import timeout
from typing_extensions import Self

from hummingbot.core.utils.async_utils import safe_ensure_future
from hummingbot.logger import HummingbotLogger


class AsyncCallSchedulerException(Exception):
    """
    Exception class to be raised when an error occurs during AsyncCallScheduler execution.
    """
    pass


T = TypeVar('T')


class AsyncCallSchedulerItem(NamedTuple):
    """
    A named tuple representing an item in the AsyncCallScheduler's coroutine queue.

    :param future: The Future object representing the result of the coroutine.
    :param coroutine: The coroutine to be executed by the scheduler.
    :param timeout_seconds: The number of seconds before the coroutine times out.
    :param app_warning_msg: A custom warning message to be logged in case of an error during coroutine execution.
    """
    future: Future
    coroutine: Coroutine
    timeout_seconds: float
    app_warning_msg: str = "API call error."


class AsyncCallScheduler:
    """
    A class that schedules asynchronous calls with a configurable interval and timeout.

    It provides an interface to schedule coroutines or regular functions and supports
    handling timeouts and errors.
    """
    _acs_shared_instance: Self | None = None
    _acs_logger: HummingbotLogger | None = None

    @classmethod
    def shared_instance(cls) -> Self:
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
            cls._acs_logger = logging.getLogger(__name__)  # type: ignore # HummingbotLogger not a Logger?
        return cls._acs_logger

    def __init__(self, call_interval: float = 0.01, max_queue_size: int = 100, cool_off_seconds: float = 1.0):
        """
        Initialize a new instance of the AsyncCallScheduler.

        :param call_interval: The interval between calls, in seconds.
        """
        self._call_interval: float = call_interval
        self._max_queue_size: int = max_queue_size
        self._full_cool_off: float = cool_off_seconds

        self._coro_scheduler_task: Task | None = None
        self._coro_queue: Queue[AsyncCallSchedulerItem] = Queue(maxsize=max_queue_size)
        self._is_stopping: bool = False

    @property
    def coro_queue(self) -> Queue:
        """
        Get the coroutine queue of the AsyncCallScheduler.

        :return: The coroutine queue of the AsyncCallScheduler.
        """
        return self._coro_queue

    @property
    def coro_scheduler_task(self) -> Task | None:
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
            self._is_stopping = True
            self._coro_scheduler_task.cancel()
            self._coro_scheduler_task = None

    async def _coro_scheduler(self, coro_queue: Queue[AsyncCallSchedulerItem], interval: float = 0.01) -> None:
        """
        Coroutine scheduler.

        This method continuously processes coroutines from the given coroutine queue and
        executes them with the specified timeout. It sleeps for a given interval between
        processing coroutines if the queue is empty.

        :param coro_queue: The Queue containing coroutines to be executed.
        :param interval: The interval between coroutine executions, in seconds, when the queue is empty.
        """

        async def process_coroutine() -> None:
            """
            Dequeue and process a coroutine from the coro_queue.

            This function attempts to execute the coroutine with the given timeout.
            It handles various exceptions that may occur during the execution.
            """
            item: AsyncCallSchedulerItem = await coro_queue.get()
            fut, coro, timeout_seconds, app_warning_msg = item

            try:
                async with timeout(timeout_seconds):
                    fut.set_result(await coro)
            except asyncio.CancelledError:  # The timeout expired
                fut.cancel()
                raise AsyncCallSchedulerException(f"Scheduled coroutine timed out:{coro}")

            except asyncio.InvalidStateError:  # The future is already done
                pass

            except Exception as e:
                handle_generic_exception(e, fut, app_warning_msg)

        def handle_generic_exception(e: Exception, fut: Future, app_warning_msg: str) -> None:
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
            if self._is_stopping and coro_queue.empty():
                break

            await process_coroutine()

            if coro_queue.empty():
                try:
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    raise AsyncCallSchedulerException("Scheduler sleep cancelled.")
                except Exception:
                    self.logger().error("Scheduler sleep interrupted.", exc_info=True)

    async def schedule_async_call(self,
                                  coro: Coroutine[Any, Any, T],
                                  timeout_seconds: float,
                                  app_warning_msg: str = "API call error.") -> T:
        """
        Schedule a coroutine for execution with a specified timeout.

        :param coro: The coroutine to be executed.
        :param timeout_seconds: The number of seconds before the coroutine times out.
        :param app_warning_msg: A custom warning message to be logged in case of an error during coroutine execution.
        :return: The result of the coroutine execution.
        """
        if self._coro_queue.full():
            await asyncio.sleep(self._full_cool_off)
            if self._coro_queue.full():
                raise AsyncCallSchedulerException(f"Task queue is full and seems locked"
                                                  f" (waited {self._full_cool_off} seconds).")

        fut: Future[T] = asyncio.get_event_loop().create_future()
        await self._coro_queue.put(AsyncCallSchedulerItem(
            future=fut,
            coroutine=coro,
            timeout_seconds=timeout_seconds,
            app_warning_msg=app_warning_msg))

        if self._coro_scheduler_task is None:
            self.start()
        return await fut

    class FuncProtocol(Protocol):
        def __call__(self, *args: Any) -> T:
            ...

    async def call_async(self,
                         func: FuncProtocol,
                         *args: Any,
                         timeout_seconds: float = 5.0,
                         app_warning_msg: str = "API call error.") -> T:
        """
        Schedule a regular function for asynchronous execution with a specified timeout.

        :param func: The function to be executed.
        :param args: The arguments to be passed to the function.
        :param timeout_seconds: The number of seconds before the function execution times out.
        :param app_warning_msg: A custom warning message to be logged in case of an error during function execution.
        :return: The result of the function execution.
        """
        async def async_func(*local_args) -> T:
            return await asyncio.to_thread(func, *local_args)

        coro: Coroutine[Any, Any, T] = async_func(*args)

        return await self.schedule_async_call(coro, timeout_seconds, app_warning_msg=app_warning_msg)
