from .event_listener cimport EventListener


cdef class EventReporter(EventListener):
    cdef:
        str event_source
    cdef c_call(self, object event_object)
