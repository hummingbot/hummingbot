from hummingbot.core.pubsub import PubSub


cdef class EventListener:
    def __init__(self):
        self._current_event_tag = 0
        self._current_event_caller = None

    def __call__(self, arg: any):
        raise NotImplementedError

    @property
    def current_event_tag(self) -> int:
        return self._current_event_tag

    @property
    def current_event_caller(self) -> PubSub:
        return self._current_event_caller

    cdef c_set_event_info(self, int64_t current_event_tag, PubSub current_event_caller):
        self._current_event_tag = current_event_tag
        self._current_event_caller = current_event_caller

    cdef c_call(self, object arg):
        self(arg)
