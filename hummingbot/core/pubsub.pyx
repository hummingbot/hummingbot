# distutils: language=c++
# distutils: sources=hummingbot/core/cpp/PyRef.cpp

from cpython cimport(
    PyObject,
    PyWeakref_NewRef,
    PyWeakref_GetObject
)
from cython.operator cimport(
    postincrement as inc,
    dereference as deref,
    address
)
from libcpp.vector cimport vector
from enum import Enum
import logging
import random
from typing import List

from hummingbot.logger import HummingbotLogger
from hummingbot.core.event.event_listener import EventListener
from hummingbot.core.event.event_listener cimport EventListener

class_logger = None


cdef class PubSub:
    """
    PubSub with weak references. This avoids the lapsed listener problem by periodically performing GC on dead
    event listener.

    Dead listener is done by calling c_remove_dead_listeners(), which checks whether the listener weak references are
    alive or not, and removes the dead ones. Each call to c_remove_dead_listeners() takes O(n).

    Here's how the dead listener GC is performed:

    1. c_add_listener():
       Randomly with ADD_LISTENER_GC_PROBABILITY. This assumes c_add_listener() is called frequently and so it doesn't
       make sense to do the GC every time.
    2. c_remove_listener():
       Every time. This assumes c_remove_listener() is called infrequently.
    3. c_get_listeners() and c_trigger_event():
       Every time. Both functions take O(n) already.
    """

    ADD_LISTENER_GC_PROBABILITY = 0.005

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global class_logger
        if class_logger is None:
            class_logger = logging.getLogger(__name__)
        return class_logger

    def __init__(self):
        self._events = Events()

    def add_listener(self, event_tag: Enum, listener: EventListener):
        self.c_add_listener(event_tag.value, listener)

    def remove_listener(self, event_tag: Enum, listener: EventListener):
        self.c_remove_listener(event_tag.value, listener)

    def get_listeners(self, event_tag: Enum) -> List[EventListener]:
        return self.c_get_listeners(event_tag.value)

    def trigger_event(self, event_tag: Enum, message: any):
        self.c_trigger_event(event_tag.value, message)

    cdef c_log_exception(self, int64_t event_tag, object arg):
        self.logger().error(f"Unexpected error while processing event {event_tag}.", exc_info=True)

    cdef c_add_listener(self, int64_t event_tag, EventListener listener):
        cdef:
            EventsIterator it = self._events.find(event_tag)
            EventListenersCollection new_listeners
            EventListenersCollection *listeners_ptr
            object listener_weakref = PyWeakref_NewRef(listener, None)
            PyRef listener_wrapper = PyRef(<PyObject *>listener_weakref)
        if it != self._events.end():
            listeners_ptr = address(deref(it).second)
            deref(listeners_ptr).insert(listener_wrapper)
        else:
            new_listeners.insert(listener_wrapper)
            self._events.insert(EventsPair(event_tag, new_listeners))

        if random.random() < PubSub.ADD_LISTENER_GC_PROBABILITY:
            self.c_remove_dead_listeners(event_tag)

    cdef c_remove_listener(self, int64_t event_tag, EventListener listener):
        cdef:
            EventsIterator it = self._events.find(event_tag)
            EventListenersCollection *listeners_ptr
            object listener_weakref = PyWeakref_NewRef(listener, None)
            PyRef listener_wrapper = PyRef(<PyObject *>listener_weakref)
            EventListenersIterator lit
        if it == self._events.end():
            return
        listeners_ptr = address(deref(it).second)
        lit = deref(listeners_ptr).find(listener_wrapper)
        if lit != deref(listeners_ptr).end():
            deref(listeners_ptr).erase(lit)
        self.c_remove_dead_listeners(event_tag)

    cdef c_remove_dead_listeners(self, int64_t event_tag):
        cdef:
            EventsIterator it = self._events.find(event_tag)
            EventListenersCollection *listeners_ptr
            object listener_weakref
            EventListenersIterator lit
            vector[EventListenersIterator] lit_to_remove
        if it == self._events.end():
            return
        listeners_ptr = address(deref(it).second)
        lit = deref(listeners_ptr).begin()
        while lit != deref(listeners_ptr).end():
            listener_weakref = <object>(deref(lit).get())
            if <object>(PyWeakref_GetObject(listener_weakref)) is None:
                lit_to_remove.push_back(lit)
            inc(lit)
        for lit in lit_to_remove:
            deref(listeners_ptr).erase(lit)
        if deref(listeners_ptr).size() < 1:
            self._events.erase(it)

    cdef c_get_listeners(self, int64_t event_tag):
        self.c_remove_dead_listeners(event_tag)

        cdef:
            EventsIterator it = self._events.find(event_tag)
            EventListenersCollection *listeners_ptr
            object listener_weafref
            EventListener typed_listener

        if it == self._events.end():
            return []

        retval = []
        listeners_ptr = address(deref(it).second)
        for pyref in deref(listeners_ptr):
            listener_weafref = <object>pyref.get()
            typed_listener = <object>PyWeakref_GetObject(listener_weafref)
            retval.append(typed_listener)
        return retval

    cdef c_trigger_event(self, int64_t event_tag, object arg):
        self.c_remove_dead_listeners(event_tag)

        cdef:
            EventsIterator it = self._events.find(event_tag)
            EventListenersCollection listeners
            object listener_weafref
            EventListener typed_listener
        if it == self._events.end():
            return

        # It is extremely important that this set of listeners is a C++ copy - because listeners are allowed to call
        # c_remove_listener(), which breaks the iterator if we're using the underlying set.
        listeners = deref(it).second
        for pyref in listeners:
            listener_weafref = <object>pyref.get()
            typed_listener = <object>PyWeakref_GetObject(listener_weafref)
            try:
                typed_listener.c_set_event_info(event_tag, self)
                typed_listener.c_call(arg)
            except Exception:
                self.c_log_exception(event_tag, arg)
            finally:
                typed_listener.c_set_event_info(0, None)
