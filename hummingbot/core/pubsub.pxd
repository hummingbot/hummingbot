# distutils: language=c++

from libc.stdint cimport int64_t
from libcpp.unordered_map cimport unordered_map
from libcpp.unordered_set cimport unordered_set
from libcpp.utility cimport pair
from hummingbot.core.PyRef cimport PyRef
from hummingbot.core.event.event_listener cimport EventListener

ctypedef unordered_set[PyRef] EventListenersCollection
ctypedef unordered_set[PyRef].iterator EventListenersIterator
ctypedef unordered_map[int64_t, EventListenersCollection] Events
ctypedef unordered_map[int64_t, EventListenersCollection].iterator EventsIterator
ctypedef pair[int64_t, EventListenersCollection] EventsPair


cdef class PubSub:
    cdef:
        Events _events
        object __weakref__

    cdef c_log_exception(self, int64_t event_tag, object arg)
    cdef c_add_listener(self, int64_t event_tag, EventListener listener)
    cdef c_remove_listener(self, int64_t event_tag, EventListener listener)
    cdef c_remove_dead_listeners(self, int64_t event_tag)
    cdef c_get_listeners(self, int64_t event_tag)
    cdef c_trigger_event(self, int64_t event_tag, object arg)
