#!/usr/bin/env python
import time
from abc import (
    ABCMeta,
    abstractmethod,
)
import asyncio


class UserStreamTrackerDataSource(metaclass=ABCMeta):
    @abstractmethod
    async def listen_for_user_stream(self, ev_loop: asyncio.AbstractEventLoop, output: asyncio.Queue):
        raise NotImplementedError

    @staticmethod
    async def wait_til_next_tick(seconds: float = 1.0):
        now: float = time.time()
        current_tick: int = int(now // seconds)
        delay_til_next_tick: float = (current_tick + 1) * seconds - now
        await asyncio.sleep(delay_til_next_tick)

    @property
    @abstractmethod
    def last_recv_time(self) -> float:
        raise NotImplementedError

    async def _sleep(self, delay):
        """
        Function added only to facilitate patching the sleep in unit tests without affecting the asyncio module
        """
        await asyncio.sleep(delay)
