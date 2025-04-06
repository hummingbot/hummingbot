"""
A minimal implementation of the various gevent APIs used within this codebase.
"""

import asyncio
import threading
import time
from types import (
    TracebackType,
)
from typing import (
    Any,
    Callable,
    Generic,
    Literal,
    Type,
)

from web3.exceptions import (
    Web3ValueError,
)
from web3.types import (
    TReturn,
)


class Timeout(Exception):
    """
    A limited subset of the `gevent.Timeout` context manager.
    """

    seconds = None
    exception = None
    begun_at = None
    is_running = None

    def __init__(
        self,
        seconds: float = None,
        exception: Type[BaseException] = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self.seconds = seconds
        self.exception = exception

    def __enter__(self) -> "Timeout":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException],
        exc_val: BaseException,
        exc_tb: TracebackType,
    ) -> Literal[False]:
        return False

    def __str__(self) -> str:
        if self.seconds is None:
            return ""
        return f"{self.seconds} seconds"

    @property
    def expire_at(self) -> int:
        if self.seconds is None:
            raise Web3ValueError(
                "Timeouts with `seconds == None` do not have an expiration time"
            )
        elif self.begun_at is None:
            raise Web3ValueError("Timeout has not been started")
        return self.begun_at + self.seconds

    def start(self) -> None:
        if self.is_running is not None:
            raise Web3ValueError("Timeout has already been started")
        self.begun_at = time.time()
        self.is_running = True

    def check(self) -> None:
        if self.is_running is None:
            raise Web3ValueError("Timeout has not been started")
        elif self.is_running is False:
            raise Web3ValueError("Timeout has already been cancelled")
        elif self.seconds is None:
            return
        elif time.time() > self.expire_at:
            self.is_running = False
            if isinstance(self.exception, type):
                raise self.exception(str(self))
            elif isinstance(self.exception, Exception):
                raise self.exception
            else:
                raise self

    def cancel(self) -> None:
        self.is_running = False

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
        self.check()

    async def async_sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
        self.check()


class ThreadWithReturn(threading.Thread, Generic[TReturn]):
    def __init__(
        self,
        target: Callable[..., TReturn] = None,
        args: Any = None,
        kwargs: Any = None,
    ) -> None:
        super().__init__(
            target=target,
            args=args or tuple(),
            kwargs=kwargs or {},
        )
        self.target = target
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        self._return = self.target(*self.args, **self.kwargs)

    def get(self, timeout: float = None) -> TReturn:
        self.join(timeout)
        try:
            return self._return
        except AttributeError:
            raise RuntimeError("Something went wrong.  No `_return` property was set")


class TimerClass(threading.Thread):
    def __init__(self, interval: int, callback: Callable[..., Any], *args: Any) -> None:
        threading.Thread.__init__(self)
        self.callback = callback
        self.terminate_event = threading.Event()
        self.interval = interval
        self.args = args

    def run(self) -> None:
        while not self.terminate_event.is_set():
            self.callback(*self.args)
            self.terminate_event.wait(self.interval)

    def stop(self) -> None:
        self.terminate_event.set()


def spawn(
    target: Callable[..., TReturn],
    *args: Any,
    thread_class: Type[ThreadWithReturn[TReturn]] = ThreadWithReturn,
    **kwargs: Any,
) -> ThreadWithReturn[TReturn]:
    thread = thread_class(
        target=target,
        args=args,
        kwargs=kwargs,
    )
    thread.daemon = True
    thread.start()
    return thread
