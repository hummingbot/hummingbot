from typing import Any

from hummingbot.core.event.event_listener import EventListener


class MockEventListener(EventListener):
    def __init__(self):
        super().__init__()
        self._events_count = 0
        self._last_event = None

    @property
    def events_count(self) -> int:
        return self._events_count

    @property
    def last_event(self) -> Any:
        return self._last_event

    def __call__(self, event: Any):
        self._events_count += 1
        self._last_event = event
