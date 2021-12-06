import asyncio
from collections import deque

from async_timeout import timeout
from typing import (
    List,
    Optional,
)

from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.event.events import OrderFilledEvent

cdef class EventLogger(EventListener):
    def __init__(self, event_source: Optional[str] = None):
        super().__init__()
        self._event_source = event_source
        # We limit the amount of events we keep reference to the most recent ones
        # But we keep all references to order fill events, because they are required for PnL calculation
        self._generic_logged_events = deque(maxlen=50)
        self._order_filled_logged_events = deque()
        self._logged_events = {OrderFilledEvent: self._order_filled_logged_events}
        self._waiting = {}
        self._wait_returns = {}

    @property
    def event_log(self) -> List[any]:
        return list(self._generic_logged_events) + list(self._order_filled_logged_events)

    @property
    def event_source(self) -> str:
        return self._event_source

    def clear(self):
        self._generic_logged_events.clear()
        self._order_filled_logged_events.clear()

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
        self.c_call(event_object)

    cdef c_call(self, object event_object):
        self._logged_events.get(type(event_object), self._generic_logged_events).append(event_object)
        event_object_type = type(event_object)

        should_notify = []
        for notifier, waiting_event_type in self._waiting.items():
            if event_object_type is waiting_event_type:
                should_notify.append(notifier)
                self._wait_returns[notifier] = event_object
        for notifier in should_notify:
            notifier.set()
