#!/usr/bin/env python

import asyncio
from typing import (
    Coroutine,
    Callable
)
from web3 import Web3

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

    @staticmethod
    async def call_async(func: Callable, *args):
        return await AsyncCallScheduler.shared_instance().call_async(func, *args)

    async def start_network(self):
        raise NotImplementedError

    async def stop_network(self):
        raise NotImplementedError
