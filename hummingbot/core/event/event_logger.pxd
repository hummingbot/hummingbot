from .event_listener cimport EventListener


cdef class EventLogger(EventListener):
    cdef:
        str _event_source
        object _logged_events
        object _generic_logged_events
        object _order_filled_logged_events
        dict _waiting
        dict _wait_returns
    cdef c_call(self, object event_object)
