import asyncio
from collections import deque

from async_timeout import timeout
from typing import (
    List,
    Optional,
)

from hummingbot.core.event.event_listener cimport EventListener
from hummingbot.core.event.events import OrderFilledEvent

ORDER_FILLED_EVENT_LOG_MAXLEN = 200


cdef class EventLogger(EventListener):
    def __init__(
        self,
        event_source: Optional[str] = None,
        order_filled_event_maxlen: int = ORDER_FILLED_EVENT_LOG_MAXLEN,
    ):
        super().__init__()
        if order_filled_event_maxlen <= 0:
            raise ValueError("order_filled_event_maxlen must be greater than zero")
        self._event_source = event_source
        # Event history is also persisted by MarketsRecorder. Keeping a bounded in-memory
        # window prevents high-frequency bots from retaining every fill for their lifetime.
        self._generic_logged_events = deque(maxlen=50)
        self._order_filled_logged_events = deque(maxlen=order_filled_event_maxlen)
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
        del self._waiting[notifier]
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
