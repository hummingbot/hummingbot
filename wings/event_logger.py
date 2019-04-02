#!/usr/bin/env python

import asyncio
from async_timeout import timeout
from typing import List

from wings.event_listener import EventListener


class EventLogger(EventListener):
    def __init__(self):
        super().__init__()
        self._logged_events = []
        self._waiting = {}
        self._wait_returns = {}

    @property
    def event_log(self) -> List[any]:
        return self._logged_events.copy()

    def clear(self):
        self._logged_events.clear()

    async def wait_for(self, event_type, timeout_seconds: float = 180):
        notifier = asyncio.Event()
        self._waiting[notifier] = event_type

        async with timeout(timeout_seconds):
            await notifier.wait()

        retval = self._wait_returns.get(notifier)
        if notifier in self._wait_returns:
            del self._wait_returns[notifier]
        return retval

    def __call__(self, event_object):
        self._logged_events.append(event_object)
        event_object_type = type(event_object)

        should_notify: List[asyncio.Event] = []
        for notifier, waiting_event_type in self._waiting.items():
            if event_object_type is waiting_event_type:
                should_notify.append(notifier)
                self._wait_returns[notifier] = event_object
        for notifier in should_notify:
            notifier.set()
