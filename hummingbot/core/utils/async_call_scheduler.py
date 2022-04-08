#!/usr/bin/env python

import asyncio
from async_timeout import timeout
import logging
from typing import (
    Optional,
    Coroutine,
    NamedTuple,
    Callable
)

import hummingbot
from hummingbot.logger import HummingbotLogger
from hummingbot.core.utils.async_utils import safe_ensure_future


class AsyncCallSchedulerItem(NamedTuple):
    future: asyncio.Future
    coroutine: Coroutine
    timeout_seconds: float
    app_warning_msg: str = "API call error."


class AsyncCallScheduler:
    _acs_shared_instance: Optional["AsyncCallScheduler"] = None
    _acs_logger: Optional[HummingbotLogger] = None

    @classmethod
    def shared_instance(cls):
        if cls._acs_shared_instance is None:
            cls._acs_shared_instance = AsyncCallScheduler()
        return cls._acs_shared_instance

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._acs_logger is None:
            cls._acs_logger = logging.getLogger(__name__)
        return cls._acs_logger

    def __init__(self, call_interval: float = 0.01):
        self._coro_queue: asyncio.Queue = asyncio.Queue()
        self._coro_scheduler_task: Optional[asyncio.Task] = None
        self._call_interval: float = call_interval
        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    @property
    def coro_queue(self) -> asyncio.Queue:
        return self._coro_queue

    @property
    def coro_scheduler_task(self) -> Optional[asyncio.Task]:
        return self._coro_scheduler_task

    @property
    def started(self) -> bool:
        return self._coro_scheduler_task is not None

    def start(self):
        if self._coro_scheduler_task is not None:
            self.stop()
        self._coro_scheduler_task = safe_ensure_future(
            self._coro_scheduler(
                self._coro_queue,
                self._call_interval
            )
        )

    def stop(self):
        if self._coro_scheduler_task is not None:
            self._coro_scheduler_task.cancel()
            self._coro_scheduler_task = None

    async def _coro_scheduler(self, coro_queue: asyncio.Queue, interval: float = 0.01):
        while True:
            app_warning_msg = "API call error."
            try:
                fut, coro, timeout_seconds, app_warning_msg = await coro_queue.get()
                async with timeout(timeout_seconds):
                    fut.set_result(await coro)
            except asyncio.CancelledError:
                try:
                    fut.cancel()
                except Exception:
                    pass
                raise
            except asyncio.InvalidStateError:
                # The future is already cancelled from outside. Ignore.
                pass
            except Exception as e:
                # Add exception information.
                app_warning_msg += f" [[Got exception: {str(e)}]]"
                self.logger().debug(app_warning_msg,
                                    exc_info=True,
                                    app_warning_msg=app_warning_msg)
                try:
                    fut.set_exception(e)
                except Exception:
                    pass

            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.logger().error("Scheduler sleep interrupted.", exc_info=True)

    async def schedule_async_call(self,
                                  coro: Coroutine,
                                  timeout_seconds: float,
                                  app_warning_msg: str = "API call error.") -> any:
        fut: asyncio.Future = self._ev_loop.create_future()
        self._coro_queue.put_nowait(AsyncCallSchedulerItem(fut, coro, timeout_seconds,
                                                           app_warning_msg=app_warning_msg))
        if self._coro_scheduler_task is None:
            self.start()
        return await fut

    async def call_async(self,
                         func: Callable, *args,
                         timeout_seconds: float = 5.0,
                         app_warning_msg: str = "API call error.") -> any:
        coro: Coroutine = self._ev_loop.run_in_executor(
            hummingbot.get_executor(),
            func,
            *args,
        )
        return await self.schedule_async_call(coro, timeout_seconds, app_warning_msg=app_warning_msg)
