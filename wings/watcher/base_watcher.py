#!/usr/bin/env python

import asyncio
from typing import (
    Coroutine,
    Callable
)
from web3 import Web3

import wings
from wings.async_call_scheduler import AsyncCallScheduler
from wings.pubsub import PubSub


class BaseWatcher(PubSub):
    def __init__(self, w3: Web3):
        super().__init__()
        self._w3: Web3 = w3
        self._ev_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    @staticmethod
    async def schedule_async_call(coro: Coroutine, timeout_seconds: float) -> any:
        return await AsyncCallScheduler.shared_instance().schedule_async_call(coro, timeout_seconds)

    async def async_call(self, func: Callable, *args):
        coro: Coroutine = self._ev_loop.run_in_executor(
            wings.get_executor(),
            func,
            *args,
        )
        return await self.schedule_async_call(coro, 10.0)

    async def start_network(self):
        raise NotImplementedError

    async def stop_network(self):
        raise NotImplementedError
