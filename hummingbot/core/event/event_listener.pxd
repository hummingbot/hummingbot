from libc.stdint cimport int64_t

from hummingbot.core.pubsub cimport PubSub


cdef class EventListener:
    cdef:
        object __weakref__
        int64_t _current_event_tag
        PubSub _current_event_caller

    cdef c_set_event_info(self, int64_t current_event_tag, PubSub current_event_caller)
    cdef c_call(self, object arg)
